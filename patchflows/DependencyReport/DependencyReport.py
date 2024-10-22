import csv
from pathlib import Path

import yaml

from patchwork.common.utils.progress_bar import PatchflowProgressBar
from patchwork.common.utils.step_typing import validate_steps_with_inputs
from patchwork.logger import logger
from patchwork.step import Step
from patchwork.steps import ScanDepscan



_DEFAULT_INPUT_FILE = Path(__file__).parent / "defaults.yml"


class DependencyReport(Step):
    def __init__(self, inputs: dict):
        PatchflowProgressBar(self).register_steps(ScanDepscan)

        final_inputs = yaml.safe_load(_DEFAULT_INPUT_FILE.read_text())
        final_inputs.update(inputs)

        validate_steps_with_inputs(
            set(final_inputs.keys()),
            ScanDepscan
        )

        self.inputs = final_inputs

    def run(self) -> dict:
        outputs = ScanDepscan(self.inputs).run()
        self.inputs.update(outputs)
        sbom_values = self.inputs.get("sbom_vdr_values")
        output_path = self.inputs.get("output_path")

        logger.info(f"Report is being written to {output_path}")
        with open(output_path, "w", newline="") as csvfile:
            fieldnames = ["coordinate", "version", "license", "indirect"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for component in sbom_values.get("components", []):
                coordinate = component.get("bom-ref")
                version = component.get("version", "None")
                properties = component.get("properties", [])
                indirect = "Unknown"
                is_image = False

                for property in properties:
                    if property.get("name") == "cdx:go:indirect":
                        indirect = property.get("value")

                    if property.get("name") == "oci:SrcImage":
                        is_image = True

                if is_image:
                    continue

                licenses = component.get("licenses", [])
                if len(licenses) < 1:
                    writer.writerow({
                        "coordinate": coordinate,
                        "version": version,
                        "license": "Unknown",
                        "indirect": indirect,
                    })
                    continue

                for component_license in component.get("licenses", []):
                    maybe_license = component_license.get("license", {}).get("id", "Unknown")
                    writer.writerow({
                        "coordinate": coordinate,
                        "version": version,
                        "license": maybe_license,
                        "indirect": indirect,
                    })

        logger.info(f"Report written to {output_path}")
        return self.inputs
