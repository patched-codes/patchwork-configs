# patchwork-configs

This is a repository that contains the standard set of configuration and prompts for [patchwork](https://github.com/patched-codes/patchwork). You can clone the repository and pass the folder path directly to the patchwork CLI to use it as follows:

```bash
patchwork AutoFix --config /path/to/patchwork-configs/patchflows
```

The `--config` flag takes a folder that has sub-folders for each patchflow and under them there are two files `config.yml` and `prompt.json`. These files contain the defaut configuration and prompts. You can edit and customize them based on your needs. You can also define your own patchflow and load it using the `--config` flag. As an example, there is a `HelloWorld` patchflow that can be run as follows:

```bash
patchwork HelloWorld --config ../patchwork-configs/patchflows
Hello World!
```

## List of custom patchflows

This repository also contains some additional patchflows that are implemented for specific use cases. You can use them as a basis for your own custom patchflows.

- [Fixpolyfill](/patchflows/Fixpolyfill)

