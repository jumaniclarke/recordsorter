import os
import io
import re
import csv
import hashlib
import streamlit as st
import pandas as pd
import auth

PAGE_TITLE = "Student Record Browser"


def _parse_from_iter(lines_iter):
    students = []
    current_student = None
    current_year = None

    def is_header_line(line: str) -> bool:
        s = line.strip()
        if not s:
            return True
        if s.startswith((
            "TEST",
            "COURSE RESULTS",
            "Career",
            "Degree",
            "Programme:",
            "Attributes",
            "Term,",
            "Course,",
        )):
            return True
        if set(s) <= set("-= "):
            return True
        return False

    def looks_like_student_header(fields: list[str]) -> bool:
        if len(fields) < 5:
            return False
        if not fields[0] or not fields[1]:
            return False
        if len(fields) >= 2 and "(CONTINUED" in fields[1]:
            return False
        if not re.match(r"^[A-Z0-9]{6,}$", fields[2]):
            return False
        if not fields[3].isdigit():
            return False
        if fields[0].isdigit() and len(fields[0]) == 4:
            return False
        return True

    def parse_course_segment(seg: list[str]):
        if not seg or not seg[0]:
            return None
        code = seg[0]
        result = seg[1] if len(seg) > 1 else ""
        symbol = seg[2] if len(seg) > 2 else ""
        units_attempted = seg[3] if len(seg) > 3 else ""
        units_earned = seg[4] if len(seg) > 4 else ""
        title = seg[5] if len(seg) > 5 else ""
        return {
            "code": code,
            "result": result,
            "symbol": symbol,
            "units_attempted": units_attempted,
            "units_earned": units_earned,
            "title": title,
        }

    # Use csv.reader to properly handle quoted fields with embedded commas
    reader = csv.reader(lines_iter)
    for row in reader:
        # Handle malformed rows where entire content is in one field starting with comma
        if len(row) == 1 and row[0].startswith(','):
            # Re-parse this single field as CSV
            parts = list(csv.reader([row[0]]))[0]
            parts = [p.strip() for p in parts]
        else:
            parts = [p.strip() for p in row]
        line = ",".join(row)  # Reconstruct for is_header_line check
        if is_header_line(line):
            continue

        if looks_like_student_header(parts):
            if current_student:
                students.append(current_student)
            name = f"{parts[0]}, {parts[1]}"
            campus_id = parts[2]
            emplid = parts[3]
            prgm = parts[4]
            plan = parts[6] if len(parts) > 6 else ""
            level_start = parts[8] if len(parts) > 8 else ""
            level_end = parts[9] if len(parts) > 9 else ""
            finalist = parts[10] if len(parts) > 10 else ""
            ann_code = parts[16] if len(parts) > 16 else ""
            ann_comment = parts[17] if len(parts) > 17 else ""

            current_student = {
                "name": name,
                "campus_id": campus_id,
                "emplid": emplid,
                "prgm": prgm,
                "plan": plan,
                "level_start": level_start,
                "level_end": level_end,
                "finalist": finalist,
                "annotation_code": ann_code,
                "annotation_comment": ann_comment,
                "years": [],
            }
            current_year = None
            continue

        if parts and parts[0].isdigit() and len(parts[0]) == 4:
            year = int(parts[0])
            term = parts[1] if len(parts) > 1 else ""
            prog = parts[2] if len(parts) > 2 else ""
            degree = parts[3] if len(parts) > 3 else ""
            acad_level = parts[4] if len(parts) > 4 else ""
            standing = parts[5] if len(parts) > 5 else ""
            plan_y = parts[6] if len(parts) > 6 else ""
            # Additional metrics (CB024 format has more columns) - strip semicolons
            jt = parts[11].rstrip(';') if len(parts) > 11 else ""
            je = parts[12].rstrip(';') if len(parts) > 12 else ""
            st = parts[13].rstrip(';') if len(parts) > 13 else ""
            se = parts[14].rstrip(';') if len(parts) > 14 else ""
            tt = parts[15].rstrip(';') if len(parts) > 15 else ""
            te = parts[16].rstrip(';') if len(parts) > 16 else ""
            ce = parts[17].rstrip(';') if len(parts) > 17 else ""
            wghtd_gpa = parts[18].rstrip(';') if len(parts) > 18 else ""
            term_gpa = parts[19].rstrip(';') if len(parts) > 19 else ""
            cum_gpa = parts[20].rstrip(';') if len(parts) > 20 else ""

            current_year = {
                "year": year,
                "term": term,
                "program": prog,
                "degree": degree,
                "acad_level": acad_level,
                "standing": standing,
                "plan": plan_y,
                "jt": jt,
                "je": je,
                "st": st,
                "se": se,
                "tt": tt,
                "te": te,
                "ce": ce,
                "wghtd_gpa": wghtd_gpa,
                "term_gpa": term_gpa,
                "cum_gpa": cum_gpa,
                "courses": [],
            }
            if current_student:
                current_student["years"].append(current_year)
            continue

        if current_year and parts and parts[0] == "" and len(parts) >= 2 and parts[1]:
            # Check if this is a specialization line (non-course, usually contains keywords or ends with semicolon)
            potential_spec = parts[1].rstrip(';').strip()
            # Heuristic: if parts[1] has no digits or looks like text (keywords), it's specialization
            if len(parts) <= 3 or (potential_spec and not any(c.isdigit() for c in potential_spec[:10])):
                if potential_spec and potential_spec not in ['']:
                    current_year["specialization"] = potential_spec
                    # Append specialization to programme if available
                    if current_year.get("program"):
                        current_year["program"] = f"{current_year['program']} - {potential_spec}"
                continue

        if current_year and parts and parts[0] == "":
            seg1 = parts[1:7]
            c1 = parse_course_segment(seg1)
            if c1:
                current_year["courses"].append(c1)
            sep_index = -1
            try:
                sep_index = parts.index("", 7)
            except ValueError:
                sep_index = -1
            if sep_index != -1:
                seg2 = parts[sep_index + 1: sep_index + 7]
                c2 = parse_course_segment(seg2)
                if c2:
                    current_year["courses"].append(c2)
            continue

        if line.startswith("Course Counts"):
            summary = {}
            labels = parts
            i = 1
            last_norm_label = ""
            while i < len(labels):
                label_raw = labels[i].strip()
                label_norm = label_raw.lower().strip(":")
                val = labels[i + 1].strip() if i + 1 < len(labels) else ""
                key = None
                if label_norm == "passed" and last_norm_label != "latest term: attempted":
                    key = "total_passed"
                elif label_norm == "for which units earned":
                    key = "units_earned"
                elif label_norm == "senior passed":
                    key = "senior_passed"
                elif label_norm == "junior passed":
                    key = "junior_passed"
                elif label_norm == "latest term: attempted":
                    key = "latest_term_attempted"
                elif label_norm == "passed" and last_norm_label == "latest term: attempted":
                    key = "latest_term_passed"
                if key and current_student is not None:
                    summary[key] = val
                last_norm_label = label_norm
                i += 2

            if current_student is not None and summary:
                current_student["summary"] = summary
            current_year = None
            continue

    if current_student:
        students.append(current_student)

    return students


def parse_report(file_path: str):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return _parse_from_iter(f)


def parse_report_text(text: str):
    return _parse_from_iter(text.splitlines())


def _normalize_year_label(val: str | int | float | None):
    if val is None:
        return None
    text = str(val).strip()
    if not text:
        return None
    m = re.search(r"year\s*(\d+)", text, re.IGNORECASE)
    if m:
        return f"Year {int(m.group(1))}"
    if text.isdigit():
        return f"Year {int(text)}"
    return text


def _normalize_acad_level(level: str | None):
    if not level:
        return None
    level_text = level.lower()
    mapping = {
        "first": "Year 1",
        "second": "Year 2",
        "third": "Year 3",
        "fourth": "Year 4",
        "fifth": "Year 5",
        "sixth": "Year 6",
    }
    for key, norm in mapping.items():
        if key in level_text:
            return norm
    m = re.search(r"(\d+)", level_text)
    if m:
        return f"Year {int(m.group(1))}"
    return None


def _clean_code(code: str | None):
    if code is None:
        return None
    text = str(code).strip()
    if not text:
        return None
    if text.lower() in {"nan", "none"}:
        return None
    return text.upper()


def _is_fail_course(course: dict) -> bool:
    sym = str(course.get("symbol", ""))
    if "F" in sym:
        return True
    res = str(course.get("result", "")).strip()
    try:
        if res:
            return float(res) < 50
    except ValueError:
        pass
    return False


@st.cache_data(show_spinner=False)
def load_programme_requirements(path: str):
    if not os.path.exists(path):
        return {}, {}
    try:
        df = pd.read_csv(path)
        # Normalize column names to snake_case for flexible CSV headers
        def _norm(col: str):
            return str(col).strip().lower().replace(" ", "_").replace("-", "_")
        df.columns = [_norm(c) for c in df.columns]
    except Exception:
        return {}, {}

    index: dict[str, dict[str, list[dict]]] = {}
    names: dict[str, str] = {}
    for _, row in df.iterrows():
        prog = str(
            row.get("programme_code")
            or row.get("program_code")
            or row.get("programme")
            or row.get("program")
            or ""
        ).strip()
        if not prog:
            continue
        year_label = _normalize_year_label(row.get("year"))
        course_code = _clean_code(row.get("course_code") or row.get("course"))
        alt_course = _clean_code(row.get("alternative_course") or row.get("alternative"))
        if not course_code:
            continue
        rec = {
            "course_code": course_code,
            "alternative_course": alt_course,
            "programme_name": str(
                row.get("programme_name")
                or row.get("program_name")
                or row.get("programme")
                or row.get("program")
                or ""
            ).strip(),
            "year_label": year_label,
        }
        index.setdefault(prog, {}).setdefault(year_label, []).append(rec)
        if prog not in names:
            names[prog] = rec["programme_name"]
    return index, names


def compute_student_insights(student: dict):
    """Derive extra summaries: program changes, repeated fails, actual year count, weakest year pass rate."""
    years = student.get("years", [])

    # Program change tracking
    program_sequence = []
    for yr in years:
        prog = yr.get("program")
        if prog:
            program_sequence.append(prog)
    program_changes = []
    if program_sequence:
        last = program_sequence[0]
        for prog in program_sequence[1:]:
            if prog != last:
                program_changes.append(prog)
            last = prog
    program_change_count = len(program_changes)
    # Build display string including initial program if changes exist
    if program_sequence:
        first_prog = program_sequence[0]
    else:
        first_prog = ""
    program_change_list = [first_prog] + program_changes if program_change_count else [first_prog] if first_prog else []

    # Fail detection helper
    def is_fail(course: dict):
        sym = str(course.get("symbol", ""))
        if "F" in sym:
            return True
        res = str(course.get("result", "")).strip()
        try:
            if res:
                return float(res) < 50
        except ValueError:
            pass
        return False

    # Repeated failed courses
    fail_attempts = {}
    for yr in years:
        for c in yr.get("courses", []):
            code = c.get("code")
            if not code:
                continue
            if is_fail(c):
                fail_attempts.setdefault(code, []).append(c)
    repeated_fails = []
    for code, attempts in fail_attempts.items():
        if len(attempts) >= 2:
            last = attempts[-1]
            res = str(last.get("result", "")).strip()
            repeated_fails.append(f"{code} ({res or last.get('symbol','')})")

    # Actual years of study (calendar years with courses)
    years_with_courses = set()
    for yr in years:
        if yr.get("courses"):
            years_with_courses.add(yr.get("year"))
    actual_year_number = len(years_with_courses)

    # Weakest year by pass rate (group terms within same calendar year)
    weakest = None  # (year, passed, attempted, rate)
    year_stats = {}
    for yr in years:
        y = yr.get("year")
        if y is None:
            continue
        for c in yr.get("courses", []):
            if not c.get("code"):
                continue
            stats = year_stats.setdefault(y, {"attempted": 0, "passed": 0})
            stats["attempted"] += 1
            if not is_fail(c):
                stats["passed"] += 1
    for y, stats in year_stats.items():
        attempted = stats["attempted"]
        passed = stats["passed"]
        if attempted <= 1:
            continue  # skip trivial years
        rate = passed / attempted if attempted else 1.0
        if weakest is None or rate < weakest[3]:
            weakest = (y, passed, attempted, rate)

    insights = {
        "program_changes": program_change_count,
        "program_change_list": program_change_list,
        "repeated_fails": repeated_fails,
        "actual_year": actual_year_number,
        "weakest_year": weakest,
    }
    return insights


@st.cache_data(show_spinner=False)
def load_students_from_text(text: str):
    return parse_report_text(text)


def main():
    st.set_page_config(page_title=PAGE_TITLE, layout="wide")
    
    # Handle OAuth callback
    if not auth.is_authenticated():
        auth.handle_oauth_callback()
    
    # Show login page if not authenticated
    if not auth.is_authenticated():
        auth.show_login_page()
        return
    
    # Main app (only shown when authenticated)
    st.title(PAGE_TITLE)

    req_path = os.path.join(os.path.dirname(__file__), "UCT_Commerce_Programme_Course_Requirements_2024_2025.csv")
    requirements_index, requirement_names = load_programme_requirements(req_path)

    # File upload and state management
    if "students" not in st.session_state:
        st.session_state.students = []
    if "index" not in st.session_state:
        st.session_state.index = 0
    uploaded = st.sidebar.file_uploader("Upload report CSV", type=["csv"], accept_multiple_files=False)
    if uploaded is not None:
        content_bytes = uploaded.getvalue()
        file_hash = hashlib.sha256(content_bytes).hexdigest()
        if st.session_state.get("file_hash") != file_hash:
            text = content_bytes.decode("utf-8", errors="ignore")
            st.session_state.students = load_students_from_text(text)
            st.session_state.index = 0
            st.session_state.position = 1
            st.session_state.file_hash = file_hash
            st.session_state.original_csv_text = text
            st.session_state.original_csv_name = uploaded.name
            if "annotations" not in st.session_state:
                st.session_state.annotations = {}
            st.session_state.original_csv_text = text
            st.session_state.original_csv_name = uploaded.name
            if "annotations" not in st.session_state:
                st.session_state.annotations = {}

    students = st.session_state.students
    last_idx = max(0, len(students) - 1)
    # Keep slider position in sync with index (1-based for display)
    if "position" not in st.session_state:
        st.session_state.position = (st.session_state.index + 1) if students else 1
    else:
        expected_pos = (st.session_state.index + 1) if students else 1
        if st.session_state.position != expected_pos:
            st.session_state.position = expected_pos

    # Sidebar navigation
    st.sidebar.subheader("Navigate")
    with st.sidebar:
        c1, c2, c3, c4 = st.columns(4)
        if c1.button("⏮"):
            st.session_state.index = 0
            st.session_state.position = 1
        if c2.button("◀"):
            st.session_state.index = max(0, st.session_state.index - 1)
            st.session_state.position = st.session_state.index + 1
        if c3.button("▶"):
            st.session_state.index = min(st.session_state.index + 1, last_idx)
            st.session_state.position = st.session_state.index + 1
        if c4.button("⏭"):
            st.session_state.index = last_idx
            st.session_state.position = last_idx + 1
        if students:
            def _on_position_change():
                st.session_state.index = min(max(0, st.session_state.position - 1), last_idx)

            st.slider(
                "Position",
                min_value=1,
                max_value=len(students),
                key="position",
                on_change=_on_position_change,
            )
            st.caption(f"Student {st.session_state.index + 1} of {len(students)}")
            
            # Student selector dropdown
            student_options = [f"{s['campus_id']} - {s['name']}" for s in students]
            current_option = student_options[st.session_state.index] if students else ""
            
            def _on_student_select():
                selected = st.session_state.student_selector
                selected_idx = student_options.index(selected)
                st.session_state.index = selected_idx
            
            st.selectbox(
                "Select by Student Number",
                options=student_options,
                index=st.session_state.index,
                key="student_selector",
                on_change=_on_student_select,
            )
            # Annotation UI
            st.subheader("Annotate")
            current_student_number = students[st.session_state.index].get("campus_id", "")
            code_key = f"code_{current_student_number}"
            comment_key = f"comment_{current_student_number}"
            radio_key = f"radio_{current_student_number}"
            curr_student = students[st.session_state.index]
            existing_code = curr_student.get("annotation_code", "")
            existing_comment = curr_student.get("annotation_comment", "")
            
            # Initialize if not present
            if code_key not in st.session_state:
                st.session_state[code_key] = existing_code or st.session_state.annotations.get(current_student_number, {}).get("code", "")
            if comment_key not in st.session_state:
                st.session_state[comment_key] = existing_comment or st.session_state.annotations.get(current_student_number, {}).get("comment", "")
            
            # Check if radio was previously set and apply before creating widgets
            if radio_key in st.session_state and st.session_state[radio_key]:
                st.session_state[code_key] = st.session_state[radio_key]
            
            st.text_input("Coding", key=code_key, label_visibility="visible")
            st.markdown("<style>.stRadio > label {margin-top: -1rem;}</style>", unsafe_allow_html=True)
            st.radio("", options=["CONT", "QUAL", "SUPP", "FECP", "FECR", "FECF"], key=radio_key, horizontal=True, index=None)
            st.text_area("Comment", key=comment_key, height=120)

            st.session_state.annotations[current_student_number] = {
                "code": st.session_state.get(code_key, ""),
                "comment": st.session_state.get(comment_key, ""),
            }

            # Download annotated CSV
            def _annotate_csv_text(original_text: str, annotations: dict[str, dict]):
                out = io.StringIO()
                writer = csv.writer(out)
                reader = csv.reader(io.StringIO(original_text))
                for row in reader:
                    parts = [p for p in row]
                    if len(parts) >= 4 and parts[2].strip() and parts[3].strip().isdigit():
                        campus_id = parts[2].strip()
                        ann = annotations.get(campus_id)
                        if ann:
                            while len(parts) <= 17:
                                parts.append("")
                            parts[16] = ann.get("code", "")
                            parts[17] = ann.get("comment", "")
                    writer.writerow(parts)
                return out.getvalue().encode("utf-8")

            if st.session_state.get("original_csv_text") and st.session_state.get("original_csv_name"):
                base_name = st.session_state.original_csv_name.rsplit(".", 1)[0]
                file_name = f"{base_name}_annotated.csv"
                data_bytes = _annotate_csv_text(st.session_state.original_csv_text, st.session_state.annotations)
                st.download_button("Download annotated CSV", data=data_bytes, file_name=file_name, mime="text/csv")

        # User info + logout anchored at bottom of sidebar
        st.markdown("---")
        auth.show_user_info_sidebar()
            
    if not students:
        st.info("Upload a report CSV to begin browsing records.")
        return

    student = students[st.session_state.index]
    insights = compute_student_insights(student)
    prgm_code = student.get("prgm", "")
    selected_req_code = None
    # Prefer explicit plan codes if they exist in requirements
    plan_candidates = []
    if student.get("plan"):
        plan_candidates.append(student["plan"].strip())
    # Most common year-level plan for this student
    from collections import Counter
    plan_counter = Counter(y.get("plan") for y in student.get("years", []) if y.get("plan"))
    if plan_counter:
        plan_candidates.append(plan_counter.most_common(1)[0][0])
    for cand in plan_candidates:
        if cand and cand in requirements_index:
            selected_req_code = cand
            break

    # Fallback: match by programme prefix (e.g., CB024*)
    if not selected_req_code and prgm_code:
        matching_req_codes = [code for code in requirements_index.keys() if code.startswith(prgm_code)]
        if matching_req_codes:
            if len(matching_req_codes) == 1:
                selected_req_code = matching_req_codes[0]
            else:
                def _label(code: str):
                    name = requirement_names.get(code, "")
                    return f"{code} — {name}" if name else code
                selected_req_code = st.selectbox(
                    "Select programme requirements mapping",
                    options=matching_req_codes,
                    format_func=_label,
                    key=f"req_select_{student.get('campus_id','')}",
                )

    if selected_req_code:
        readable = requirement_names.get(selected_req_code) or selected_req_code
        st.caption(f"Using programme requirements: {readable}")
    elif prgm_code:
        st.caption("No handbook programme requirements matched this programme/plan.")
    left, right_main = st.columns([2, 2])
    with left:
        st.subheader(student["name"])  # e.g. "Sables, Dylan Victor Mr"
        st.write(f"Campus ID: {student['campus_id']}")
        st.write(f"EmplID: {student['emplid']}")
        st.write(f"Program: {student['prgm']}")
        if student.get("plan"):
            st.write(f"Plan: {student['plan']}")
        if student.get("level_start") or student.get("level_end"):
            st.write(f"Level-Start: {student.get('level_start', '')} | Level-End: {student.get('level_end', '')}")
        if student.get("finalist"):
            st.write(f"Finalist?: {student['finalist']}")

    with right_main:
        insights_col, summary_col = st.columns(2)

        with insights_col:
            st.subheader("Progress Insights")
            prog_changes = insights.get("program_changes", 0)
            change_list = insights.get("program_change_list", [])
            prog_text = "N/A"
            if change_list:
                cleaned = [p for p in change_list if p]
                prog_text = f"x{prog_changes} (" + ", ".join(cleaned) + ")" if prog_changes else cleaned[0]
            st.write(f"Programme changes: {prog_text}")

            repeated = insights.get("repeated_fails", [])
            rep_text = "; ".join(repeated) if repeated else "None"
            st.write(f"Repeated failed courses: {rep_text}")

            actual_year = insights.get("actual_year") or "N/A"
            st.write(f"Actual year of study: {actual_year}")

            weakest = insights.get("weakest_year")
            if weakest:
                y, passed, attempted, rate = weakest
                st.write(f"Weakest year: {y} ({passed}/{attempted} passed)")
            else:
                st.write("Weakest year: N/A")

        with summary_col:
            st.subheader("Summary")
            summary = student.get("summary", {})
            if summary:
                label_map = {
                    "total_passed": "Passed",
                    "units_earned": "Units Earned",
                    "senior_passed": "Senior Passed",
                    "junior_passed": "Junior Passed",
                    "latest_term_attempted": "Latest Term: Attempted",
                    "latest_term_passed": "Latest Term: Passed",
                }
                rows = [{"Metric": label_map.get(k, k), "Value": v} for k, v in summary.items()]
                if rows:
                    df_sum = pd.DataFrame(rows)
                    st.dataframe(df_sum, hide_index=True, width='stretch')
            else:
                st.caption("No summary available.")

    # Years and courses (tabs with most recent first)
    years = student.get("years", [])
    if years:
        years_sorted = sorted(years, key=lambda y: y.get("year", 0), reverse=True)

        # Group terms by academic level
        level_groups = []  # list of (label, [years]) preserving order
        level_map = {}
        for yr in years_sorted:
            level_label = _normalize_acad_level(yr.get("acad_level")) or yr.get("acad_level") or f"Year {yr.get('year','')}"
            if level_label not in level_map:
                level_map[level_label] = []
                level_groups.append((level_label, level_map[level_label]))
            level_map[level_label].append(yr)

        labels = [lbl for lbl, _ in level_groups]
        outstanding_label = None
        has_requirements = bool(selected_req_code and requirements_index.get(selected_req_code, {}))
        if has_requirements:
            outstanding_label = "Outstanding"
            labels.append(outstanding_label)

        tabs = st.tabs(labels)
        main_tabs = tabs if outstanding_label is None else tabs[:-1]
        outstanding_tab = None if outstanding_label is None else tabs[-1]

        for tab, (level_label, level_years) in zip(main_tabs, level_groups):
            with tab:
                st.markdown(f"**{level_label}**")
                meta_bits = []
                # Show distinct standing/specialisation/degree/program across the level
                standings = {y.get("standing") for y in level_years if y.get("standing")}
                specs = {y.get("specialization") for y in level_years if y.get("specialization") and " - " not in y.get("program", "")}
                degrees = {y.get("degree") for y in level_years if y.get("degree")}
                progs = {y.get("program") for y in level_years if y.get("program")}
                if standings:
                    meta_bits.append(f"Standing: {', '.join(sorted(standings))}")
                if specs:
                    meta_bits.append(f"Specialisation: {', '.join(sorted(specs))}")
                if degrees:
                    meta_bits.append(f"Degree: {', '.join(sorted(degrees))}")
                if progs:
                    meta_bits.append(f"Program: {', '.join(sorted(progs))}")
                if meta_bits:
                    st.caption(" | ".join(meta_bits))

                # Collect metrics across level (latest first)
                metrics = []
                latest_year = level_years[0]
                for label, key in [("JT", "jt"), ("JE", "je"), ("ST", "st"), ("SE", "se"), ("TT", "tt"), ("TE", "te"), ("CE", "ce"), ("Wghtd GPA", "wghtd_gpa"), ("Term GPA", "term_gpa"), ("Cum GPA", "cum_gpa")]:
                    val = latest_year.get(key)
                    if val:
                        metrics.append((label, val))
                if metrics:
                    metrics_text = " | ".join([f"**{label}:** {value}" for label, value in metrics])
                    st.markdown(metrics_text)

                prog_reqs = requirements_index.get(selected_req_code, {}) if selected_req_code else {}
                level_reqs = prog_reqs.get(level_label, []) if prog_reqs else []
                # Programme-wide required sets (across all years in the selected plan)
                prog_req_main = set()
                prog_req_alt = set()
                for _yl, _reqs in (prog_reqs or {}).items():
                    for _r in _reqs:
                        mc = _clean_code(_r.get("course_code"))
                        ac = _clean_code(_r.get("alternative_course"))
                        if mc:
                            prog_req_main.add(mc)
                        if ac:
                            prog_req_alt.add(ac)

                combined_rows = []
                # Passed anywhere across the student's record (for requirement satisfaction)
                passed_codes_all = {
                    _clean_code(c.get("code"))
                    for yy in student.get("years", [])
                    for c in yy.get("courses", [])
                    if _clean_code(c.get("code")) and not _is_fail_course(c)
                }
                taken_codes = {
                    _clean_code(c.get("code"))
                    for yr in level_years
                    for c in yr.get("courses", [])
                    if _clean_code(c.get("code"))
                }

                # Required sets for this level
                req_main = {r.get("course_code") for r in level_reqs if r.get("course_code")}
                req_alt = {r.get("alternative_course") for r in level_reqs if r.get("alternative_course")}

                # Add attempted courses across all terms in this level
                for yr in level_years:
                    term_code = yr.get("term", "")
                    for c in yr.get("courses", []):
                        code = _clean_code(c.get("code")) or ""
                        is_required = code in prog_req_main or code in prog_req_alt
                        passed_anywhere = code in passed_codes_all
                        if is_required:
                            status = "Completed" if passed_anywhere else "Outstanding"
                        else:
                            status = "Not Required"
                        combined_rows.append({
                            "Year": yr.get("year", ""),
                            "Sem": term_code,
                            "Course": code,
                            "%/Grade": c.get("result", ""),
                            "Symbol": c.get("symbol", ""),
                            "Units Attempted": c.get("units_attempted", ""),
                            "Course Name": c.get("title", ""),
                            "Status": status,
                        })

                # Add outstanding requirements (not attempted or not passed anywhere)
                if level_reqs:
                    for req in level_reqs:
                        course_code = _clean_code(req.get("course_code"))
                        alt_course = _clean_code(req.get("alternative_course"))
                        display = course_code if not alt_course else f"{course_code} (alt: {alt_course})"
                        satisfied = (course_code in passed_codes_all) or (alt_course and alt_course in passed_codes_all)
                        if satisfied:
                            continue
                        combined_rows.append({
                            "Year": "",
                            "Sem": "",
                            "Course": display,
                            "%/Grade": "",
                            "Symbol": "",
                            "Units Attempted": "",
                            "Course Name": "",
                            "Status": "Outstanding",
                        })
                elif prog_reqs:
                    st.caption("No mapped programme requirements for this academic level.")

                if combined_rows:
                    df = pd.DataFrame(combined_rows)

                    def _highlight_fail(row):
                        sym = str(row.get('Symbol', ''))
                        if 'F' in sym:
                            return ['background-color: #ffe5e5; color: #8b0000'] * len(row)
                        return [''] * len(row)

                    try:
                        styled = df.style.apply(_highlight_fail, axis=1)
                        st.dataframe(styled, hide_index=True, width='stretch')
                    except Exception:
                        st.dataframe(df, hide_index=True, width='stretch')
                else:
                    st.info("No courses listed for this level.")

        if outstanding_tab is not None:
            with outstanding_tab:
                st.subheader("Outstanding courses (programme-wide)")
                prog_reqs = requirements_index.get(selected_req_code, {}) if selected_req_code else {}
                taken_all = {
                    _clean_code(c.get("code"))
                    for yr in years_sorted
                    for c in yr.get("courses", [])
                    if _clean_code(c.get("code"))
                }
                passed_all = {
                    _clean_code(c.get("code"))
                    for yr in years_sorted
                    for c in yr.get("courses", [])
                    if _clean_code(c.get("code")) and not _is_fail_course(c)
                }
                # Build pass details per course for sorting (recency and grade)
                term_order = {"R": 1, "W": 2, "S": 3}
                passed_details: dict[str, list[dict]] = {}
                for yr in years_sorted:
                    yv = yr.get("year")
                    tv = (yr.get("term") or "").strip().upper()[:1]
                    t_ord = term_order.get(tv, 0)
                    for c in yr.get("courses", []):
                        code = _clean_code(c.get("code"))
                        if not code or _is_fail_course(c):
                            continue
                        res = c.get("result", "")
                        try:
                            grade = float(res) if str(res).strip() != "" else None
                        except Exception:
                            grade = None
                        passed_details.setdefault(code, []).append({
                            "year": int(yv) if isinstance(yv, (int, float)) else yv,
                            "term_order": t_ord,
                            "grade": grade,
                        })

                sort_mode = st.radio(
                    "Similar sort by",
                    options=["Most recent", "Highest grade"],
                    horizontal=True,
                    key=f"similar_sort_mode_{student.get('campus_id','')}",
                )
                outstanding_rows = []
                for year_label, reqs in prog_reqs.items():
                    for req in reqs:
                        course_code = _clean_code(req.get("course_code"))
                        alt_course = _clean_code(req.get("alternative_course"))
                        completed = course_code in taken_all or (alt_course and alt_course in taken_all)
                        if completed:
                            continue
                        display = course_code if not alt_course else f"{course_code} (alt: {alt_course})"
                        # Similar courses: same subject and year level passed anywhere (e.g., ECO3xxx for ECO3020F)
                        base_code = course_code or alt_course or ""
                        similar_list = []
                        if base_code:
                            m = re.match(r"^([A-Z]+)(\d)", base_code)
                            if m:
                                subj = m.group(1)
                                year_level = m.group(2)
                                prefix = subj + year_level
                                # candidates: same subject + year level
                                candidates = [c for c in passed_all if c and c.startswith(prefix)]
                                def most_recent_key(code: str):
                                    dets = passed_details.get(code, [])
                                    if not dets:
                                        return (-1, -1)
                                    latest = max(dets, key=lambda d: (d.get("year") or -1, d.get("term_order") or -1))
                                    return (latest.get("year") or -1, latest.get("term_order") or -1)
                                def best_grade_key(code: str):
                                    dets = passed_details.get(code, [])
                                    if not dets:
                                        return -1.0
                                    grades = [d.get("grade") for d in dets if d.get("grade") is not None]
                                    return max(grades) if grades else -1.0
                                if sort_mode == "Most recent":
                                    similar_list = sorted(candidates, key=lambda c: (most_recent_key(c)[0], most_recent_key(c)[1], best_grade_key(c)), reverse=True)
                                else:
                                    similar_list = sorted(candidates, key=lambda c: (best_grade_key(c), most_recent_key(c)[0], most_recent_key(c)[1]), reverse=True)
                        similar_str = ", ".join(similar_list)
                        outstanding_rows.append({
                            "Year": year_label or "",
                            "Required Course": display,
                            "Similar courses completed": similar_str,
                        })
                if outstanding_rows:
                    st.dataframe(pd.DataFrame(outstanding_rows), hide_index=True, width='stretch')
                else:
                    st.success("All mapped programme requirements are completed.")


if __name__ == "__main__":
    main()
