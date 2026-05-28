"""Module to generate benchmark reports"""

import csv
import os
import re
import json
import html


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
    reader = csv.DictReader(file)
    log_data = []
    for row in reader:
        msg = (row.get("message") or "").strip()
        stage = (row.get("stage") or "").strip()
        pipeline = (row.get("pipeline") or "").strip()
        core = (row.get("core") or "").strip()
        proc_col = (row.get("process") or "").strip()
        ts = (row.get("timestamp") or "").strip()

        # extract PPID and elapsed from message
        ppid_match = re.search(r"PPID[:=]\s*(\d+)", msg)
        elapsed_match = re.search(r"elapsed[:=]\s*([\d\.]+)", msg)

        ppid = ppid_match.group(1) if ppid_match else ""
        pid = proc_col
        elapsed = elapsed_match.group(1) if elapsed_match else "0"

        cmd_field = stage if stage and stage != "THREAD" else pipeline
        if cmd_field and ("/" in cmd_field or "\\" in cmd_field):
            # show basename in table
            cmd_basename = os.path.basename(cmd_field)
        else:
            cmd_basename = cmd_field

        entry = {
            "PID": [str(pid)],
            "PPID": [str(ppid)],
            "TID": [],
            "CPUID": [core] if core != "" else [],
            "ELAPSED": [elapsed] if elapsed != "" else ["0"],
            "CMD": [cmd_basename],
            "STAGE": [cmd_field],
            "TS": [ts],
        }
        log_data.append(entry)

    column_labels = ["PID", "PPID", "TID", "CPUID", "ELAPSED", "CMD", "STAGE", "TS"]
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
            - "PPID" (str): Parent PID.
            - "CPUID" (set[int] | set[str]): Set of CPU IDs used by the process (if available).
            - "TID" (set): Set of thread IDs associated with the process.
            - "CMD" (str): Command/short name of the process.
            - "ELAPSED_LIST" (list): List of (elapsed: float, core, ts, stage) tuples.
            - "ELAPSED" (float): Maximum elapsed time (in seconds) for the process.
    """

    log_data = ps_data["data"]
    result = {}

    for entry in log_data:
        pid = (entry.get("PID") or [""])[0]
        if not pid:
            continue

        if pid not in result:
            result[pid] = {
                "PPID": (entry.get("PPID") or [""])[0],
                "CMD": (entry.get("CMD") or [""])[0],
                "TID": set(),
                "CPUID": set(),
                "ELAPSED_LIST": [],  # list of (elapsed:float, core, ts, stage)
                "ELAPSED": 0.0,  # max
            }

        # parse ELAPSED for this row
        try:
            elapsed_val = float((entry.get("ELAPSED") or ["0"])[0])
        except (ValueError, TypeError):
            elapsed_val = 0.0
        core_vals = entry.get("CPUID", []) or []
        core = core_vals[0] if core_vals else ""
        ts = (entry.get("TS") or [""])[0] if (entry.get("TS") or []) else ""
        stage = (entry.get("STAGE") or [""])[0]

        result[pid]["ELAPSED_LIST"].append((elapsed_val, core, ts, stage))
        result[pid]["ELAPSED"] = max(result[pid]["ELAPSED"], elapsed_val)

        # Add CPUID(s)
        for c in core_vals:
            if c == "":
                continue
            try:
                result[pid]["CPUID"].add(int(c))
            except Exception:
                result[pid]["CPUID"].add(c)

    return result


def _escape_table_cell(s: str) -> str:
    """Escape a value for safe use inside a Markdown table cell.

    Args:
        s (str | Any): Value to escape. If None, an empty string is returned.

    Returns:
        str: Escaped, newline-free string safe for inclusion in a Markdown cell.
    """
    if s is None:
        return ""
    return str(s).replace("|", "\\|").replace("\n", " ").replace("\r", "")


def ps_entry_to_line(pid, process_info):
    """
    Convert a process entry into a Markdown table row.

    Args:
        pid (str): Process ID.
        process_info (dict): Dictionary containing process information with keys:
            - "CMD" (str or list[str]): Command or command components for the process.
            - "TID" (set[int] or list[int]): Set/list of thread IDs associated with the process.
            - "CPUID" (set[int] or list[int], optional): Set/list of CPU IDs used by the process (if available).
            - "ELAPSED_LIST" (list): List of (elapsed: float, core, ts, stage) occurrences.
            - "ELAPSED" (float): Maximum elapsed time (seconds) for the process.

    Returns:
        str: A string representing a Markdown table row for the process entry.
    """
    cmd = process_info.get("CMD", "") or ""
    ppid = process_info.get("PPID", "")
    cpuid_vals = list(process_info.get("CPUID", []) or [])
    try:
        cpus = ", ".join(map(str, sorted(cpuid_vals)))
    except Exception:
        cpus = ", ".join(map(str, cpuid_vals)) if cpuid_vals else ""
    elapsed_list = process_info.get("ELAPSED_LIST", []) or []
    finished = [e for e, _, _, _ in elapsed_list if (e or 0) > 0.0]
    count_finished = len(finished)
    total = sum(finished) if count_finished else 0.0
    maximum = max(finished) if finished else 0.0
    avg = (total / count_finished) if count_finished else 0.0
    summary = f"max={maximum:.2f}s sum={total:.2f}s avg={avg:.2f}s ({count_finished})"
    return f"| {_escape_table_cell(cmd)} | {pid} | {ppid} | {summary} | {cpus} |\n"


def ps_description(ps_data):
    """Generate process summary and detailed sections in Markdown.

    Produces:
      - a summary table sorted by ELAPSED (the maximum observed elapsed time per PID, descending)
        containing for each PID: short command, PID, PPID, statistics (max/sum/avg/(occ)) and CPUs;
      - detailed sections per PID listing finished occurrences (elapsed > 0) with elapsed, core, timestamp and stage.

    Args:
        ps_data (dict): Dictionary with keys "column_labels" and "data" as returned by read_ps_data().

    Returns:
        str: Markdown content (summary table + per-PID detail sections) ready to be inserted into the template.
    """
    processed = process_data(ps_data)

    # summary Markdown table header
    header = (
        "| Command | PID | PPID | Stats (max/sum/avg/(occ)) | CPUs |\n"
        "| ------- | --- | ---- | ------------------------ | ---- |\n"
    )
    rows = []
    for pid, info in sorted(
        processed.items(), key=lambda item: item[1].get("ELAPSED", 0.0), reverse=True
    ):
        rows.append(ps_entry_to_line(pid, info))

    parts = [header + "".join(rows)]

    # details per PID as Markdown titled blocks with Markdown tables (only finished events)
    for pid, info in sorted(
        processed.items(), key=lambda item: item[1].get("ELAPSED", 0.0), reverse=True
    ):
        el_list = info.get("ELAPSED_LIST", []) or []
        finished_events = [t for t in el_list if (t[0] or 0) > 0.0]
        if not finished_events:
            continue
        detail = []
        detail.append("**Details for PID {} (PPID {}):**\n\n".format(pid, info.get("PPID", "")))
        detail.append("| elapsed (s) | core | timestamp | stage |\n")
        detail.append("| ----------- | ---- | --------- | ----- |\n")
        for elapsed_val, core, ts, stage in finished_events:
            detail.append(
                "| {:.2f} | {} | {} | {} |\n".format(
                    elapsed_val,
                    _escape_table_cell(core or "-"),
                    _escape_table_cell(ts or "-"),
                    _escape_table_cell(stage or "-"),
                )
            )
        parts.append("".join(detail))

    return "\n\n".join(parts)


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
            # Use an HTML <img> so the output HTML displays the image directly.
            try:
                out_dir = os.path.dirname(output_file_path) or "."
                img_path = os.path.relpath(figure_path, out_dir)
            except Exception:
                img_path = figure_path
            full_data["benchmon_plot"] = f'<img src="{html.escape(img_path)}" alt="Benchmon plot of resource usage" />'

        # Trim leading blank lines from inserted HTML blocks to avoid extra gaps
        for k, v in list(full_data.items()):
            if isinstance(v, str):
                full_data[k] = v.lstrip("\n")

        # Final report rendering
        fill_template_from_file(self.template_file_path, output_file_path, full_data)
