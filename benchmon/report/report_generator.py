"""Module to generate benchmark reports"""

import re
import json


def fill_template(template: str, values: dict):
    """
    Replaces <key> placeholders in a string with values from a dictionary.

    If a key is missing, the placeholder stays unchanged.

    Args:
        template (str): String with placeholders like <name>.
        values (dict): Keys and replacement values.

    Returns:
        str: Updated string with replacements.
    """

    def replace(match):
        key = match.group(1)
        return str(values.get(key, match.group(0)))

    return re.sub(r"<(\w+)>", replace, template)


def fill_template_from_file(
    template_file_path: str, output_file_path: str, values: dict
):
    """Use a template file to generate a document. Uses the dictionary passed as an argument to replace tokens in the
    template by their corresponding values.

    Args:
        template_file_path (str): Path to the template file to use.
        output_file_path (str): Path of the generated output file.
        values (dict): Associates tokens in the template file to the content used to replace them.
    """
    with open(template_file_path, "r", encoding="utf-8") as f:
        template = f.read()

    output = fill_template(template, values)

    with open(output_file_path, "w", encoding="utf-8") as f:
        f.write(output)


def generate_hidden(title: str, content: str):
    """Generate a string containing the Markdown description of a hidden section.

    Args:
        title (str): Section title.
        content (str): Section content.

    Returns:
        str: Markdown code for a hidden section.
    """
    output = (
        "<details>\n" + "<summary>" + title + "</summary>\n" + content + "</details>\n"
    )
    return output


def spack_description(data):
    """Generate a Markdown description for a Spack package based on its JSON description.

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

    infos = (
        "\n"
        + "- **Version**: "
        + version
        + "\n"
        + "- **Platform**: "
        + platform
        + "\n"
        + "- **OS**: "
        + os
        + "\n"
        + "- **CPU architecture**: "
        + cpu_arch
        + "\n"
        + "- **Compiler**: "
        + compiler
        + "\n"
    )

    return generate_hidden(name, infos)


def spack_env_description(spack_data):
    """Generate a Markdown description of a Spack environment from a JSON description.

    Args:
        spack_data: JSON description of a Spack environment.

    Returns:
        str: Markdown description of the environment.
    """
    if spack_data is None:
        return ""
    text = ""
    for _, data in spack_data.items():
        text = text + spack_description(data[0])

    return generate_hidden("Loaded packages", text)


def python_env_description(data):
    """Generate a Markdown description of a Python environment from its JSON description.

    Args:
        data: JSON description of a Python environement.

    Returns:
        str: Markdown description of the environment.
    """
    if data is None:
        return ""

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
    _MARKDOWN_CHARACTERS_TO_ESCAPE = set(r"$\`*_{}[]<>()#+-.!|")  # noqa: N806
    return "".join(
        f"\\{character}" if character in _MARKDOWN_CHARACTERS_TO_ESCAPE else character
        for character in text
    )


def env_description(data):
    """Generate a Markdown description of a shell environment from its JSON description.

    Args:
        data: JSON description of a shell environment.

    Returns:
        str: Markdown description of the shell environment.
    """
    if data is None:
        return ""

    text = "\n"
    for key, item in data.items():
        text = text + "- " + key + ": " + escaped_markdown(item) + "\n"

    return text


def hardware_description(hw_data):
    if hw_data is None:
        return ""

    template = """
- CPUs:
    - model name: <CPU_Model>
    - number of cores: <Cores_per_socket>
    - threads per core: <Threads_per_core>
    - sockets and NUMA organisation: <Sockets> socket(s), <NUMA_nodes> NUMA nodes
    - min frequency: <CPU_Min_Speed_MHz> MHz
    - max frequency: <CPU_Max_Speed_MHz> MHz
    - L1d cache: <L1d_cache> per socket
    - L1i cache: <L1i_cache> per socket
    - L2 cache: <L2_cache> per socket
    - L3 cache: <L3_cache> per socket
- Memory:
    - RAM: <ram_gib> GiB (<ram_per_core_gib> GiB per core)
    - Swap: <swap_gib> GiB

"""

    cpu_data = hw_data["cpu"][1]
    ram_gib = hw_data["memory"]["mem"]["total"] / (1024 * 1024 * 1024)
    ram_per_core_gib = ram_gib / (
        hw_data["cpu"][1]["Sockets"] * hw_data["cpu"][1]["Cores_per_socket"]
    )
    swap_gib = hw_data["memory"]["swap"]["total"] / (1024 * 1024 * 1024)
    memory_data = {
        "ram_gib": str(round(ram_gib, 2)),
        "ram_per_core_gib": str(round(ram_per_core_gib, 2)),
        "swap_gib": round(swap_gib, 2),
    }

    return fill_template(template, cpu_data | memory_data)


def read_ps_data(file):
    """
    Read and parse a ps log file into a structured format.

    Args:
        file (TextIO): File object representing the ps log file.

    Returns:
        dict: A dictionary containing:
            - "column_labels" (list[str]): List of column labels from the log file.
            - "data" (list[dict]): List of dictionaries, each representing a parsed log entry.
    """
    log_data = []
    columns_sizes = {
        "PPID": 1,
        "PID": 1,
        "TID": 1,
        "CPUID": 1,
        "ELAPSED": 1,
        "STARTED": 5,
        "CMD": -1,
    }

    column_labels = []
    for line in file:
        # Extract column labels
        if line.strip().startswith("#"):
            column_labels = line.strip().split()[1:]  # Remove the leading "#"
            continue

        columns = line.split()
        log_entry = {}
        idx = 0

        for label in column_labels:
            size = columns_sizes.get(label, 1)
            new_idx = idx + size if size != -1 else len(columns)

            if new_idx > len(columns):
                log_entry = None
                break

            log_entry[label] = columns[idx:new_idx]
            idx = new_idx

        if log_entry:
            log_data.append(log_entry)

    return {"column_labels": column_labels, "data": log_data}


def process_data(ps_data):
    """
    Process parsed ps log data to aggregate information by process ID.

    Args:
        ps_data (dict): A dictionary containing:
            - "column_labels" (list[str]): List of column labels from the log file.
            - "data" (list[dict]): List of dictionaries, each representing a parsed log entry.

    Returns:
        dict: A dictionary where each key is a process ID (PID) and the value is another dictionary containing:
            - "CPUID" (set[int], optional): Set of CPU IDs used by the process (if available in column labels).
            - "TID" (set[int]): Set of thread IDs associated with the process.
            - "CMD" (list[str]): Command line arguments of the process.
            - "ELAPSED" (int): Maximum elapsed time (in seconds) for the process.
    """
    column_labels = ps_data["column_labels"]
    log_data = ps_data["data"]
    result = {}

    for entry in log_data:
        pid = entry["PID"][0]  # Process ID
        if pid not in result:
            # Initialize the process entry in the result dictionary
            result[pid] = {"TID": set(), "CMD": entry["CMD"], "ELAPSED": 0}
            if "CPUID" in column_labels:
                result[pid]["CPUID"] = set()

        # Update the maximum elapsed time for the process
        result[pid]["ELAPSED"] = max(result[pid]["ELAPSED"], int(entry["ELAPSED"][0]))

        # Add the thread ID to the set of thread IDs
        result[pid]["TID"].add(int(entry["TID"][0]))

        # Add the CPU ID to the set of CPU IDs (if available)
        if "CPUID" in column_labels:
            result[pid]["CPUID"].add(int(entry["CPUID"][0]))

    return result


def ps_entry_to_line(pid, process_info):
    """
    Convert a process entry into a Markdown table row.

    Args:
        pid (str): Process ID.
        process_info (dict): Dictionary containing process information with keys:
            - "CMD" (list[str]): Command line arguments of the process.
            - "TID" (set[int]): Set of thread IDs associated with the process.
            - "CPUID" (set[int], optional): Set of CPU IDs used by the process (if available).
            - "ELAPSED" (int): Maximum elapsed time (in seconds) for the process.

    Returns:
        str: A string representing a Markdown table row for the process entry.
    """
    row = f"| {process_info['CMD'][0]} | {pid} | "
    row += ", ".join(map(str, process_info["TID"])) + " | "
    row += " ".join(process_info["CMD"]) + " | "

    if "CPUID" in process_info:
        row += ", ".join(map(str, process_info["CPUID"])) + " | "
    else:
        row += " | "

    row += f"{process_info['ELAPSED']} |\n"

    return row


def ps_description(ps_data):
    """
    Génère une table Markdown des processus, triés par durée totale,
    en prenant le temps maximal par PID.

    Args:
        ps_data (dict): Contient "column_labels" et "data".

    Returns:
        str: Table Markdown avec nom et durée totale.
    """
    total_elapsed = {}
    processed_data = process_data(ps_data)

    for _, data in processed_data.items():
        name = " ".join(data["CMD"])
        total_elapsed[name] = total_elapsed.get(name, 0) + data["ELAPSED"]

    sorted_items = sorted(total_elapsed.items(), key=lambda x: x[1], reverse=True)
    lines = [
        "| Process name | Elapsed time (s) |",
        "| ------------ | ---------------- |"
    ]
    for name, elapsed in sorted_items:
        lines.append(f"| {name} | {elapsed:.2f} |")

    return "\n".join(lines)


class ReportGenerator:
    """Class used to generate a benchmark report from benchmon results."""

    def __init__(self, template_file_path: str):
        """Initialize ReportGenerator"""
        self.template_file_path = template_file_path

    def write(
        self,
        hw_report_path: str,
        sw_report_path: str,
        ps_path: str,
        figure_path: str,
        output_file_path: str,
    ):
        """
        Generates a benchmark report using hardware, software, process, and figure data.

        Args:
            hw_report_path (str): Path to the hardware description JSON file.
            sw_report_path (str): Path to the software description JSON file.
            ps_path (str): Path to the process statistics file.
            figure_path (str): Path to the benchmark figure image.
            output_file_path (str): Path to save the final rendered report.
        """
        full_data = {}

        # Hardware section
        if hw_report_path:
            with open(hw_report_path, "r") as file:
                hw_data = json.load(file)
            hw_str = "\n".join(
                generate_hidden(node, hardware_description(node_data))
                for node, node_data in hw_data.items()
            )
            full_data["hardware_description"] = hw_str

        # Software section
        if sw_report_path:
            with open(sw_report_path, "r") as file:
                sw_data = json.load(file)

            spack_env_str = ""
            python_env_str = ""
            env_str = ""

            for node, node_data in sw_data.items():
                if node_data.get("spack_dependencies"):
                    spack_env_str += generate_hidden(
                        node, spack_env_description(node_data["spack_dependencies"])
                    )
                if node_data.get("pyenv"):
                    python_env_str += generate_hidden(
                        node, python_env_description(node_data["pyenv"])
                    )
                if node_data.get("env"):
                    env_str += generate_hidden(node, env_description(node_data["env"]))

            full_data["spack_dependencies"] = spack_env_str or "None"
            full_data["python_environment"] = python_env_str or "None"
            full_data["environment_variables"] = env_str or "None"

        # Process statistics section
        if ps_path:
            with open(ps_path, "r") as file:
                ps_data = read_ps_data(file)
            full_data["ps_data"] = ps_description(ps_data)

        # Figure section
        if figure_path:
            full_data["benchmon_plot"] = (
                f"![Benchmon plot of resource usage]({figure_path})"
            )

        # Final report rendering
        fill_template_from_file(self.template_file_path, output_file_path, full_data)
