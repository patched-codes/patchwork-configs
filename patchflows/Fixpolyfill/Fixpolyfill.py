from pathlib import Path
import yaml
import tempfile
import os
from tabulate import tabulate

from github import Github, GithubException
from gitlab import Gitlab
from gitlab.exceptions import GitlabAuthenticationError, GitlabGetError

from patchwork.logger import logger
from patchwork.step import Step
from patchwork.patchflows import AutoFix

_DEFAULT_INPUT_FILE = Path(__file__).parent / "config.yml"
_DEFAULT_PROMPT_JSON = Path(__file__).parent / "prompt.json"

class Fixpolyfill(Step):
    def __init__(self, inputs: dict):
        final_inputs = yaml.safe_load(_DEFAULT_INPUT_FILE.read_text())
                    
        if final_inputs is None:
            final_inputs = {}
        final_inputs.update(inputs)
            
        if "prompt_template_file" not in final_inputs.keys():
            final_inputs["prompt_template_file"] = _DEFAULT_PROMPT_JSON
        
        self.inputs = final_inputs

    def run(self) -> dict:
        if 'github_org_name' in self.inputs:
            return self.run_github_org()
        elif 'gitlab_org_name' in self.inputs:
            return self.run_gitlab_org()
        else:
            return self.run_single()

    def run_single(self) -> dict:
        outputs = AutoFix(self.inputs).run()
        return outputs

    def run_github_org(self) -> dict:
        if 'github_api_key' not in self.inputs:
            raise ValueError("github_api_key is not provided in the inputs")
        
        g = Github(self.inputs['github_api_key'])
        
        try:
            # First, try to get the organization
            org = g.get_organization(self.inputs['github_org_name'])
            repos = org.get_repos()
        except GithubException as e:
            if e.status == 404:
                # If organization is not found, try to get it as a user
                try:
                    user = g.get_user(self.inputs['github_org_name'])
                    logger.warning(f"'{self.inputs['github_org_name']}' is a user account, not an organization. Processing user's repositories.")
                    repos = user.get_repos()
                except GithubException:
                    logger.error(f"Could not find organization or user '{self.inputs['github_org_name']}'. Please check the name and your access rights.")
                    raise ValueError(f"Invalid GitHub organization or user name: {self.inputs['github_org_name']}")
            elif e.status == 401:
                logger.error("Authentication failed. Please check your GitHub API key.")
                raise ValueError("Invalid GitHub API key")
            else:
                logger.error(f"An error occurred while accessing the GitHub API: {str(e)}")
                raise
        
        return self._process_repos(repos)

    def run_gitlab_org(self) -> dict:
        if 'gitlab_api_key' not in self.inputs:
            raise ValueError("gitlab_api_key is not provided in the inputs")
        
        gl = Gitlab(self.inputs.get('gitlab_url', 'https://gitlab.com'), private_token=self.inputs['gitlab_api_key'])
        
        try:
            gl.auth()
            group = gl.groups.get(self.inputs['gitlab_org_name'])
            repos = group.projects.list(all=True)
        except GitlabAuthenticationError:
            logger.error("Authentication failed. Please check your GitLab API key.")
            raise ValueError("Invalid GitLab API key")
        except GitlabGetError as e:
            if e.response_code == 404:
                # If group is not found, try to get it as a user
                try:
                    user = gl.users.list(username=self.inputs['gitlab_org_name'])[0]
                    logger.warning(f"'{self.inputs['gitlab_org_name']}' is a user account, not a group. Processing user's projects.")
                    repos = user.projects.list(all=True)
                except IndexError:
                    logger.error(f"Could not find group or user '{self.inputs['gitlab_org_name']}'. Please check the name and your access rights.")
                    raise ValueError(f"Invalid GitLab group or user name: {self.inputs['gitlab_org_name']}")
            else:
                logger.error(f"An error occurred while accessing the GitLab API: {str(e)}")
                raise
        
        return self._process_repos(repos)

    def _process_repos(self, repos) -> dict:
        results = []
        original_dir = os.getcwd()
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            for repo in repos:
                print(f"Processing {repo.name}...")
                repo_path = Path(tmp_dir) / repo.name
                try:
                    os.chdir(tmp_dir)  # Change to temp directory before cloning
                    clone_url = repo.clone_url if hasattr(repo, 'clone_url') else repo.http_url_to_repo
                    os.system(f"git clone {clone_url} {repo.name}")
                    os.chdir(repo_path)
                    
                    inputs_copy = self.inputs.copy()
                    inputs_copy['repo_path'] = str(repo_path)
                    outputs = AutoFix(inputs_copy).run()
                    
                    results.append({
                        'repo': repo.name,
                        'pr_url': outputs.get("pr_url", "")
                    })
                except Exception as e:
                    logger.error(f"Error processing repository {repo.name}: {str(e)}")
                    results.append({
                        'repo': repo.name,
                        'pr_url': f"Error: {str(e)}"
                    })
                finally:
                    os.chdir(original_dir)  # Always return to the original directory
        
        self.print_summary(results)
        return self.inputs

    def print_summary(self, results):
        table = tabulate(results, headers="keys", tablefmt="grid")
        print("\nSummary of processed repositories:")
        print(table)