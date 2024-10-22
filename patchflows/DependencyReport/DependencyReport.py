from pathlib import Path

import yaml
import pandas as pd

from patchwork.common.utils.progress_bar import PatchflowProgressBar
from patchwork.common.utils.step_typing import validate_steps_with_inputs
from patchwork.logger import logger
from patchwork.step import Step
from patchwork.steps import (
    ScanDepscan,
)


_DEFAULT_INPUT_FILE = Path(__file__).parent / "defaults.yml"


class DependencyReport(Step):
    def __init__(self, inputs: dict):
        PatchflowProgressBar(self).register_steps(ScanDepscan)

        final_inputs = yaml.safe_load(_DEFAULT_INPUT_FILE.read_text())
        final_inputs.update(inputs)

        validate_steps_with_inputs(
            set(final_inputs.keys()).union({"prompt_values"}),
            ScanDepscan
        )

        self.inputs = final_inputs

    def run(self) -> dict:
        outputs = ScanDepscan(self.inputs).run()
        self.inputs.update(outputs)
        sbom_values = self.inputs.get("sbom_vdr_values")

        csv_data = []
        for component in sbom_values.get("components", []):
            coordinate = component.get("bom-ref")
            version = component.get("version", "None")
            properties = component.get("properties", [])
            direct = "Unknown"

            if not coordinate.startswith("pkg:golang"):
                continue

            for property in properties:
                if property.get("name") == "cdx:go:indirect":
                    direct = property.get("value")

            licenses = component.get("licenses", [])
            if len(licenses) < 1:
                csv_data.append({
                    "coordinate": coordinate,
                    "version": version,
                    "license": "Unknown",
                    "direct": direct,
                })
                continue

            for component_license in component.get("licenses", []):
                maybe_license = component_license.get("license", {}).get("id", "Unknown")
                csv_data.append({
                    "coordinate": coordinate,
                    "version": version,
                    "license": maybe_license,
                    "direct": direct,
                })

        df = pd.DataFrame.from_records(csv_data)
        output_path = self.inputs.get("output_path")
        df.to_csv(output_path, index=False)
        logger.info(f"Report written to {output_path}")
        return self.inputs
