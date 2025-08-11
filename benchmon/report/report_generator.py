"""Module to generate benchmark reports"""
import re
import json


def fill_template(template_file_path: str, output_file_path: str, values: dict):
    """Use a template file to generate a document. Uses the dictionary passed as an argument to replace tokens in the
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
    """Generate a string containing the Markdown description of a hidden section.

    Args:
        title (str): Section title.
        content (str): Section content.

    Returns:
        str: Markdown code for a hidden section.
    """
    output = "<details>\n" + "<summary>" + title + "</summary>\n" + content + "</details>\n"
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

    infos = "\n" + "- **Version**: " + version + "\n" + "- **Platform**: " + platform + "\n" + "- **OS**: " + os + \
            "\n" + "- **CPU architecture**: " + cpu_arch + "\n" + "- **Compiler**: " + compiler + "\n"

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

    return generate_hidden("Unroll list", text)


def hardware_description(hw_data):
    """Generate a dictionary of Markdown hardware configuration descriptions from its JSON counterpart.

    Args:
        hw_data: JSON description of a hardware configuration.

    Returns:
        str: Markdown description of the hardware configuration.
    """
    if hw_data is None:
        return ""

    # Directly pulls CPU information as a Json dictionary
    cpu_data = hw_data["cpu"][1]

    # Extracts memory information
    ram_gib = hw_data["memory"]["mem"]["total"] / (1024 * 1024 * 1024)
    ram_per_core_gib = ram_gib / \
        (hw_data["cpu"][1]["Sockets"] * hw_data["cpu"][1]["Cores_per_socket"])
    swap_gib = hw_data["memory"]["swap"]["total"] / (1024 * 1024 * 1024)
    memory_data = {"ram_gib": str(round(ram_gib, 2)), "ram_per_core_gib": str(round(ram_per_core_gib, 2)),
                   "swap_gib": round(swap_gib, 2)}

    return cpu_data | memory_data


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
        "CMD": -1
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
            result[pid] = {
                "TID": set(),
                "CMD": entry["CMD"],
                "ELAPSED": 0
            }
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
    # Start the row with the process name (first command argument) and process ID
    row = f"| {process_info['CMD'][0]} | {pid} | "

    # Add thread IDs as a comma-separated list
    row += ", ".join(map(str, process_info["TID"])) + " | "

    # Add the full command line as a space-separated string
    row += " ".join(process_info["CMD"]) + " | "

    # Add CPU IDs if available
    if "CPUID" in process_info:
        row += ", ".join(map(str, process_info["CPUID"])) + " | "
    else:
        row += " | "  # Empty column if CPUID is not available

    # Add the total elapsed time
    row += f"{process_info['ELAPSED']} |\n"

    return row


def ps_description(ps_data):
    """
    Generate a Markdown table description of process data from parsed ps log data.

    Args:
        ps_data (dict): A dictionary containing:
            - "column_labels" (list[str]): List of column labels from the log file.
            - "data" (list[dict]): List of dictionaries, each representing a parsed log entry.

    Returns:
        str: A string representing a Markdown table of the process data.
    """
    # Process the raw ps data to aggregate information by process ID
    processed_data = process_data(ps_data)
    column_labels = ps_data["column_labels"]

    # Initialize the Markdown table header
    table_header = [
        "| Process name | Process ID | Thread IDs | Command line |",
        "| ------------ | ---------- | ---------- | ------------ |"
    ]

    # Add a column for CPU IDs if available in the column labels
    if "CPUID" in column_labels:
        table_header[0] += " CPU IDs |"
        table_header[1] += " ------- |"

    # Add the column for total elapsed time
    table_header[0] += " Total elapsed time (s) |"
    table_header[1] += " ---------------------- |"

    # Initialize the table content
    table_content = ""

    # Populate the table rows with process data
    for pid, process_info in processed_data.items():
        table_content += ps_entry_to_line(pid, process_info)

    # Combine the header and content into the final Markdown table
    return "\n".join(table_header) + "\n" + table_content


class ReportGenerator:
    """Class used to generate a benchmark report from benchmon results.
    """

    def __init__(self, template_file_path: str):
        """Initialize ReportGenerator"""
        self.template_file_path = template_file_path

    def write(self, hw_report_path: str, sw_report_path: str, ps_path: str, figure_path: str, output_file_path: str):
        """Write a benchmark report from benchmon results.

        Args:
            hw_report_file (str): Path to the hardware description file.
            sw_report_file (str): Path to the software description file.
            output_file_path (str): Path to the output file.
        """
        full_data = {}
        if hw_report_path:
            with open(hw_report_path, 'r') as file:
                hw_data = json.load(file)
            full_data = full_data | hardware_description(hw_data)

        if sw_report_path:
            with open(sw_report_path, 'r') as file:
                sw_data = json.load(file)
            full_data = full_data | {"spack_dependencies": spack_env_description(sw_data["spack_dependencies"])}

        if ps_path:
            with open(ps_path, 'r') as file:
                ps_data = read_ps_data(file)
            full_data = full_data | {"ps_data": ps_description(ps_data)}

        if figure_path:
            full_data = full_data | {"benchmon_plot": f'![Benchmon plot of resource usage]({figure_path})'}

        full_data = full_data | {"python_environment": python_env_description(sw_data["pyenv"])}
        full_data = full_data | {"environment_variables": env_description(sw_data["env"])}

        fill_template(self.template_file_path, output_file_path, full_data)
