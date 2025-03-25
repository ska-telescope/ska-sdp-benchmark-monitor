import re
import json

def fill_template(template_file_path: str, output_file_path: str, values: dict):
    """Uses a template file to generate a document. Uses the dictionary passed as an argument to replace tokens in the
    template by their corresponding values.

    Args:
        template_file_path (str): Path to the template file to use.
        output_file_path (str): Path of the generated output file.
        values (dict): Associates tokens in the template file to the content used to replace them.
    """
    with open(template_file_path, "r", encoding="utf-8") as f:
        template = f.read()

    def replace(match):
        key = match.group(1)
        return str(values.get(key, match.group(0)))

    output = re.sub(r"<(\w+)>", replace, template)

    with open(output_file_path, "w", encoding="utf-8") as f:
        f.write(output)


def generate_hidden(title: str, content: str):
    """Generates a string containing the Markdown description of a hidden section.

    Args:
        title (str): Section title.
        content (str): Section content.

    Returns:
        str: Markdown code for a hidden section.
    """
    output = "<details>\n" + \
            "<summary>" + title + "</summary>\n" + \
            content + \
            "</details>\n"
    return output


def spack_description(data):
    """Generates a Markdown description for a Spack package based on its JSON description.

    Args:
        data: JSON description of a Spack package.

    Returns:
        str: Markdown description of the package.
    """
    name = data["name"]
    version = data["version"]
    platform = data["arch"]["platform"]
    os = data["arch"]["platform_os"]
    cpu_arch = data["arch"]["target"]
    compiler = data["compiler"]["name"] + "/" + data["compiler"]["version"]

    if not (type(cpu_arch) is str):
        cpu_arch = cpu_arch["name"]

    infos =                                         "\n" + \
            "- **Version**: "          + version  + "\n" + \
            "- **Platform**: "         + platform + "\n" + \
            "- **OS**: "               + os       + "\n" + \
            "- **CPU architecture**: " + cpu_arch + "\n" + \
            "- **Compiler**: "         + compiler + "\n"

    return generate_hidden(name, infos)


def spack_env_description(spack_data):
    """Generates a Markdown description of a Spack environment from a JSON description.

    Args:
        spack_data: JSON description of a Spack environment.

    Returns:
        str: Markdown description of the environment.
    """
    text = ""
    for _, data in spack_data.items():
        text = text + spack_description(data[0])

    return generate_hidden("Loaded packages", text)


def python_env_description(data):
    """Generates a Markdown description of a Python environment from its JSON description.

    Args:
        data: JSON description of a Python environement.

    Returns:
        str: Markdown description of the environment.
    """
    environment_name = data["env"]

    text = "\n"
    for item in data["packages"]:
        name = item["name"]
        version = item["version"]
        text = text + "- " + name + "/" + version + "\n"

    return generate_hidden("Name: " + environment_name, text)


def escaped_markdown(text: str) -> str:
    """Escapes Markdown special characters from a string.

    Args:
        text (str): String to process.

    Returns:
        str: String with escaped Markdown special characters.
    """
    _MARKDOWN_CHARACTERS_TO_ESCAPE = set(r"$\`*_{}[]<>()#+-.!|")
    return "".join(
        f"\\{character}" if character in _MARKDOWN_CHARACTERS_TO_ESCAPE else character
        for character in text
    )


def env_description(data):
    """Generates a Markdown description of a shell environment from its JSON description.

    Args:
        data: JSON description of a shell environment.

    Returns:
        str: Markdown description of the shell environment.
    """
    text = "\n"
    for key, item in data.items():
        text = text + "- " + key + ": " + escaped_markdown(item) + "\n"

    return generate_hidden("Unroll list", text)


def hardware_description(hw_data):
    """Generates a dictionary of Markdown hardware configuration descriptions from its JSON counterpart.

    Args:
        hw_data: JSON description of a hardware configuration.

    Returns:
        str: Markdown description of the hardware configuration.
    """
    # Directly pulls CPU information as a Json dictionary
    cpu_data = hw_data["cpu"][1]

    # Extracts memory information
    ram_gib = hw_data["memory"]["mem"]["total"] / (1024 * 1024 * 1024)
    ram_per_core_gib = ram_gib / \
        (hw_data["cpu"][1]["Sockets"] * hw_data["cpu"][1]["Cores_per_socket"])
    swap_gib = hw_data["memory"]["swap"]["total"] / (1024 * 1024 * 1024)
    memory_data = {"ram_gib": str(round(ram_gib, 2)),
                "ram_per_core_gib": str(round(ram_per_core_gib, 2)),
                "swap_gib": round(swap_gib, 2)}

    return cpu_data | memory_data

class ReportGenerator:
    """Class used to generate a benchmark report from benchmon results.
    """
    def __init__(self, template_file_path: str):
        self.template_file_path = template_file_path

    def write(self, hw_report_file: str, sw_report_file: str, output_file_path: str):
        """Writes a benchmark report from benchmon results.

        Args:
            hw_report_file (str): Path to the hardware description file.
            sw_report_file (str): Path to the software description file.
            output_file_path (str): Path to the output file.
        """
        with open(hw_report_file, 'r') as file:
            hw_data = json.load(file)

        with open(sw_report_file, 'r') as file:
            sw_data = json.load(file)

        hardware_data = hardware_description(hw_data)
        soft_data = {"spack_dependencies": spack_env_description(sw_data["spack_dependencies"])}
        pyenv_data = {"python_environment": python_env_description(sw_data["pyenv"])}
        env_data = {"environment_variables": env_description(sw_data["env"])}

        data = hardware_data | soft_data | pyenv_data | env_data

        fill_template(self.template_file_path, output_file_path, data)
