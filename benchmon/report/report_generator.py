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
    """Generate an HTML <details> block. Title is escaped, content is expected to be HTML."""
    return f"<details>\n<summary>{html.escape(title)}</summary>\n{content}\n</details>\n"

def _html_ul(items):
    """Render a simple HTML unordered list from already-escaped items."""
    if not items:
        return ""
    return "<ul>\n" + "\n".join(f"<li>{item}</li>" for item in items) + "\n</ul>\n"

def spack_description(data):
    """HTML description for a Spack package (returns a <details> block)."""
    if not data:
        return ""
    name = html.escape(data.get("name", ""))
    version = html.escape(str(data.get("version", "")))
    platform = html.escape(str(data.get("arch", {}).get("platform", "")))
    osname = html.escape(str(data.get("arch", {}).get("platform_os", "")))
    cpu_arch = data.get("arch", {}).get("target", "")
    if not isinstance(cpu_arch, str):
        cpu_arch = cpu_arch.get("name", "")
    cpu_arch = html.escape(str(cpu_arch))
    compiler = html.escape(str(data.get("compiler", {}).get("name", ""))) + "/" + html.escape(str(data.get("compiler", {}).get("version", "")))

    infos = [
        f"<strong>Version</strong>: {version}",
        f"<strong>Platform</strong>: {platform}",
        f"<strong>OS</strong>: {osname}",
        f"<strong>CPU architecture</strong>: {cpu_arch}",
        f"<strong>Compiler</strong>: {compiler}",
    ]
    return generate_hidden(name or "spack package", _html_ul(infos))

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
    """Return Python environment as an HTML <details> block with a list of packages."""
    if data is None:
        return ""
    env_name = html.escape(data.get("env", ""))
    items = []
    for item in data.get("packages", []):
        items.append(html.escape(item.get("name", "")) + " / " + html.escape(item.get("version", "")))
    return generate_hidden(f"Name: {env_name}", _html_ul(items))

def escaped_markdown(text: str) -> str:
    """Escape Markdown special characters by prefixing them with a backslash.
    Returns empty string for None input.
    """
    if text is None:
        return ""
    to_escape = set(r"$\`*_{}[]<>()#+-.!|")
    s = str(text)
    return "".join(f"\\{c}" if c in to_escape else c for c in s)

def env_description(data):
    """Return shell environment variables as an HTML unordered list."""
    if data is None:
        return ""
    items = []
    for key, val in data.items():
        items.append(f"{html.escape(str(key))}: {html.escape(str(val))}")
    return _html_ul(items)

def hardware_description(hw_data):
    """Return HTML content (no outer <details>) describing hardware as an unordered list."""
    if hw_data is None:
        return ""

    cpu_data = hw_data["cpu"][1]
    ram_gib = hw_data["memory"]["mem"]["total"] / (1024 * 1024 * 1024)
    ram_per_core_gib = ram_gib / (
        cpu_data.get("Sockets", 1) * cpu_data.get("Cores_per_socket", 1)
    )
    swap_gib = hw_data["memory"]["swap"]["total"] / (1024 * 1024 * 1024)
    items = [
        f"<strong>Model name</strong>: {html.escape(str(cpu_data.get('CPU_Model','')))}",
        f"<strong>Number of cores</strong>: {html.escape(str(cpu_data.get('Cores_per_socket','')))}",
        f"<strong>Threads per core</strong>: {html.escape(str(cpu_data.get('Threads_per_core','')))}",
        f"<strong>Sockets and NUMA organisation</strong>: {html.escape(str(cpu_data.get('Sockets','')))} socket(s), {html.escape(str(cpu_data.get('NUMA_nodes','')))} NUMA nodes",
        f"<strong>Min frequency</strong>: {html.escape(str(cpu_data.get('CPU_Min_Speed_MHz','N/A')))} MHz",
        f"<strong>Max frequency</strong>: {html.escape(str(cpu_data.get('CPU_Max_Speed_MHz','N/A')))} MHz",
        f"<strong>L1d cache</strong>: {html.escape(str(cpu_data.get('L1d_cache','')))} per socket",
        f"<strong>L1i cache</strong>: {html.escape(str(cpu_data.get('L1i_cache','')))} per socket",
        f"<strong>L2 cache</strong>: {html.escape(str(cpu_data.get('L2_cache','')))} per socket",
        f"<strong>L3 cache</strong>: {html.escape(str(cpu_data.get('L3_cache','')))} per socket",
        f"<strong>RAM</strong>: {round(ram_gib,2)} GiB ({round(ram_per_core_gib,2)} GiB per core)",
        f"<strong>Swap</strong>: {round(swap_gib,2)} GiB",
    ]
    return _html_ul(items)

def read_ps_data(file):
    """
    Parse timing_mapping_report.csv
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
    Aggregate CSV entries by PID:
    - stores ELAPSED_LIST of (elapsed, core, timestamp, stage)
    - ELAPSED holds the observed maximum elapsed (used for sorting)
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
    """Escape table-breaking chars for Markdown cells."""
    if s is None:
        return ""
    return str(s).replace("|", "\\|").replace("\n", " ").replace("\r", "")

def ps_entry_to_line(pid, process_info):
    """Return one summary table row computed from finished occurrences (elapsed>0)."""

    cmd = process_info.get("CMD", "") or ""
    ppid = process_info.get("PPID", "")
    cpus = ", ".join(map(str, sorted(process_info.get("CPUID", []), key=lambda x: int(x) if isinstance(x, (str, int)) and str(x).isdigit() else x)))
    elapsed_list = process_info.get("ELAPSED_LIST", [])
    finished = [e for e, _, _, _ in elapsed_list if e > 0.0]
    count_finished = len(finished)
    total = sum(finished) if count_finished else 0.0
    maximum = max(finished) if finished else 0.0
    avg = (total / count_finished) if count_finished else 0.0
    summary = f"max={maximum:.2f}s sum={total:.2f}s avg={avg:.2f}s ({count_finished})"
    return f"| {_escape_table_cell(cmd)} | {pid} | {ppid} | {summary} | {cpus} |\n"


def ps_description(ps_data):
    """Render process summary and details as HTML (summary table + details tables)."""
    processed = process_data(ps_data)

    # summary HTML table
    summary_rows = []
    summary_rows.append("<table>")
    summary_rows.append("<thead><tr><th>Command</th><th>PID</th><th>PPID</th><th>Stats (max/sum/avg/(occ))</th><th>CPUs</th></tr></thead>")
    summary_rows.append("<tbody>")
    for pid, info in sorted(processed.items(), key=lambda item: item[1].get("ELAPSED", 0.0), reverse=True):
        cmd = html.escape(info.get("CMD","") or "")
        ppid = html.escape(str(info.get("PPID","")))
        cpus = ", ".join(map(str, sorted(info.get("CPUID", []), key=lambda x: int(x) if isinstance(x, (str, int)) and str(x).isdigit() else x)))
        elapsed_list = info.get("ELAPSED_LIST", [])
        finished = [e for e, _, _, _ in elapsed_list if e > 0.0]
        count_finished = len(finished)
        total = sum(finished) if count_finished else 0.0
        maximum = max(finished) if finished else 0.0
        avg = (total / count_finished) if count_finished else 0.0
        summary = f"max={maximum:.2f}s sum={total:.2f}s avg={avg:.2f}s ({count_finished})"
        summary_rows.append(f"<tr><td>{cmd}</td><td>{pid}</td><td>{ppid}</td><td>{html.escape(summary)}</td><td>{html.escape(cpus)}</td></tr>")
    summary_rows.append("</tbody></table>")

    parts = ["\n".join(summary_rows)]

    # details per PID as HTML <details> with HTML table (only finished events)
    for pid, info in sorted(processed.items(), key=lambda item: item[1].get("ELAPSED", 0.0), reverse=True):
        el_list = info.get("ELAPSED_LIST", [])
        finished_events = [t for t in el_list if (t[0] or 0) > 0.0]
        if not finished_events:
            continue
        rows = []
        rows.append("<table>")
        rows.append("<thead><tr><th>elapsed (s)</th><th>core</th><th>timestamp</th><th>stage</th></tr></thead>")
        rows.append("<tbody>")
        for elapsed_val, core, ts, stage in finished_events:
            rows.append(f"<tr><td>{elapsed_val:.2f}</td><td>{html.escape(str(core or '-'))}</td><td>{html.escape(str(ts or '-'))}</td><td>{html.escape(stage or '-')}</td></tr>")
        rows.append("</tbody></table>")
        title = f"Details for PID {pid} (PPID {info.get('PPID','')})"
        parts.append(generate_hidden(title, "\n".join(rows)))

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
