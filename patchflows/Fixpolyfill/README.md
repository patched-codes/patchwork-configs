# Polyfill Supply Chain Attack, Patched!

Recently, there has been a supply chain attack on the CDN service, polyfill.io, that was delivering malicious JavaScript code. A malicious actor took control
of the domain and used to deliver malware to over 100k website that relied on the CDN service. 

Semgrep posted on their [blog](https://semgrep.dev/blog/2024/protect-your-code-from-the-polyfill-supply-chain-attack) a new rule that can help detect the use of polyfill in your code. Along with semgrep, we can use [patchwork](hhttps://github.com/patched-codes/patchwork) to detect and fix the use of polyfill by either removing it fully from code or replacing it with a new implementation from [cloudflare](https://blog.cloudflare.com/polyfill-io-now-available-on-cdnjs-reduce-your-supply-chain-risk).

We already have an [AutoFix](https://github.com/patched-codes/patchwork/blob/main/patchwork/patchflows/AutoFix/README.md) patchflow that works quite well
to fix vulnerabilities in the code. AutoFix uses Semgrep OSS to scan the repo for issues. We can pass the new rule as an extra argument to the patchflow to detect this particular issue as follows:

```
 patchwork AutoFix semgrep_extra_args='--config r/3qUkGp2/semgrep.polyfill-compromise' 
```

This will detect the fix and automatically generate a pull request that fixes it. You can see an example run [here](https://github.com/codelion/example-python/pull/48).

The patchwork framework is very easy to extend and customize. To enable users to handle this particular case well we have created this custom patchflow called **Fixpolyfill**. With the custom patchflow you can just run:

```
patchwork Fixpolyfill --config=../patchwork-configs/patchflows
```

This makes it a lot easier to run the patchflow as the required config is already present in the config.yml file [here](https://github.com/patched-codes/patchwork-configs/blob/main/patchflows/Fixpolyfill/config.yml#L6). We have also modified the default AutoFix [prompt](https://github.com/patched-codes/patchwork-configs/blob/main/patchflows/Fixpolyfill/prompt.json) to be more specific for this particular issue. With just config and prompt changes one can make a simple reciepe from a patchflow that can be reused across different repos to detect and fix the polyfill issue.

To make it easy to run the patchflow across your entire GitHub (or GitLab) org we have added a couple of options, if you run with the `github_org_name`, the patchflow will run across all the repos that your GitHub token has access to and generate a summary at the end as follows:

```
patchwork Fixpolyfill --config=../patchwork-configs/patchflows github_org_name=codelion
'codelion' is a user account, not an organization. Processing user's repositories.
Processing AltoroJ-Workshop...
Cloning into 'AltoroJ-Workshop'...
remote: Enumerating objects: 691, done.
remote: Counting objects: 100% (98/98), done.
remote: Compressing objects: 100% (46/46), done.
remote: Total 691 (delta 74), reused 53 (delta 52), pack-reused 593
Receiving objects: 100% (691/691), 4.57 MiB | 15.71 MiB/s, done.
Resolving deltas: 100% (290/290), done.
Finished AutoFix: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████▉| 100/100 [00:03<00:00, 25.1it/s]
...
Processing analyze-aws-lambda...
Cloning into 'analyze-aws-lambda'...
...


Summary of processed repositories:
+-------------------------------------------------------------------------+----------------------------------------------------+
| repo                                                                    | pr_url                                             |
+=========================================================================+====================================================+
| AltoroJ-Workshop                                                        |                                                    |
+-------------------------------------------------------------------------+----------------------------------------------------+
| analyze-aws-lambda                                                      |                                                    |
+-------------------------------------------------------------------------+----------------------------------------------------+
| ASDL2017                                                                |                                                    |
+-------------------------------------------------------------------------+----------------------------------------------------+
| AutoBot                                                                 |                                                    |
+-------------------------------------------------------------------------+----------------------------------------------------+
| ...
+-------------------------------------------------------------------------+----------------------------------------------------+
| example-python                                                          | https://github.com/codelion/example-python/pull/48 |
+-------------------------------------------------------------------------+----------------------------------------------------+
| faststream                                                              |                                                    |
+-------------------------------------------------------------------------+----------------------------------------------------+
|...
+-------------------------------------------------------------------------+----------------------------------------------------+
```
