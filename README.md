# 🎓 AI-Assisted Timetable Generator

An AI-assisted academic timetable generation and optimization system built using **Python** and **Google OR-Tools CP-SAT**.

The system reads the provided Excel workbook and automatically generates a timetable while handling teacher conflicts, section conflicts, room conflicts, valid time slots, required teaching sessions, and timetable optimization.

---

## 🎯 Problem Statement

Creating an academic timetable manually is difficult because many constraints must be satisfied at the same time.

The system is designed to ensure that:

* A teacher is not assigned to two classes at the same time.
* A section does not have two subjects at the same time.
* Every required teaching session is scheduled.
* Only valid days and time periods are used.
* A room is not assigned to multiple classes simultaneously.
* Valid rooms and configured room restrictions are respected.
* Combined sections are handled correctly.
* Timetable quality is improved by reducing unnecessary gaps and late periods.

This problem is treated as a **Constraint Satisfaction and Combinatorial Optimization Problem**.

---

## 🧠 Approach

This project uses **Google OR-Tools CP-SAT** as the main AI-assisted optimization approach.

Traditional Machine Learning learns patterns from historical data and predicts outputs. Timetable generation is different because the system must construct a valid combination of:

```text
Teacher + Course + Section + Day + Period + Room
```

while satisfying strict constraints.

Therefore, **Constraint Programming and Combinatorial Optimization** are more suitable than traditional supervised Machine Learning for this problem.

### Overall Workflow

```text
Excel Workbook
      ↓
Data Loading & Preprocessing
      ↓
Session Generation
      ↓
Input Validation
      ↓
CP-SAT Optimization
      ↓
Day + Period Assignment
      ↓
Room Assignment
      ↓
Independent Validation
      ↓
Excel + CSV + Reports
```

---

## 🏗️ Two-Phase Scheduling Approach

The system uses two phases to reduce optimization complexity.

### Phase 1 — CP-SAT Optimization

Google OR-Tools CP-SAT determines:

```text
Session → Day + Period
```

The solver handles:

* Required session scheduling
* Teacher conflicts
* Section conflicts
* Combined sections
* Valid days
* Valid periods
* Existing timetable preferences
* Teacher gap reduction
* Section gap reduction
* Late-period penalties

### Phase 2 — Room Assignment

After the solver determines the day and period, rooms are assigned separately.

More restricted courses, including lab courses, can be prioritized during room assignment.

The final timetable is then independently validated for:

* Room conflicts
* Valid rooms
* Room restrictions

This approach reduces model complexity compared with directly solving:

```text
Session × Day × Period × Room
```

for every possible assignment.

---

# 🔒 Constraints

## Hard Constraints

The following constraints must not be violated:

### 1. Every Required Session Must Be Scheduled

Every generated teaching session must receive exactly one:

```text
Day + Time Period
```

### 2. No Teacher Conflict

A teacher cannot teach multiple classes during the same day and time period.

### 3. No Section Conflict

A section cannot attend multiple subjects at the same time.

### 4. Combined Section Handling

Combined sections such as:

```text
BCS-1E/3E
```

are expanded into their individual sections so that conflicts can be detected correctly.

### 5. Valid Days

Sessions can only be assigned to configured valid days.

### 6. Valid Time Periods

Sessions can only use configured active timetable periods.

### 7. No Room Conflict

The same room cannot be assigned to multiple sessions at the same day and time.

### 8. Valid Rooms

Assigned rooms must come from the rooms detected and configured from the supplied dataset.

### 9. Session Duration

Each session occupies one configured timetable period.

### 10. Room Restrictions

Configured room restrictions and eligibility rules are checked during validation.

---

## 📈 Soft Optimization Objectives

After satisfying the hard constraints, the solver attempts to improve timetable quality.

### Reduce Late Period Usage

Later periods are penalized so earlier periods are preferred where possible.

### Reduce Section Gaps

The solver attempts to reduce unnecessary idle periods between classes for a section.

Example:

```text
08:30 → Class
10:00 → Empty
11:30 → Class
```

### Reduce Teacher Gaps

The same principle is applied to teacher schedules to reduce unnecessary idle periods.

### Preserve Valid Existing Placements

Valid placements from the existing timetable can be used as preferences so useful assignments are preserved where possible.

---

# 📂 Input Data

The project uses the supplied Excel workbook:

```text
data/FSC_F26_TT_v1.0.2_06082026.xlsx
```

Configured course sheets:

* CS
* SE
* DS
* AI
* CY
* CI

Master timetable sheet:

```text
Combined TT
```

The system processes information about:

* Teachers/Instructors
* Courses
* Subjects
* Sections
* Programs
* Credit hours
* Course categories
* Existing timetable placements
* Days
* Time periods
* Rooms

---

# 📅 Scheduling Configuration

## Available Days

```text
Mon
Tue
Wed
Thu
Fri
Sat
```

## Active Time Periods

```text
08:30-10:00
10:00-11:30
11:30-13:00
13:00-14:30
14:30-16:00
16:00-17:30
17:30-19:00
```

Each session occupies one configured **90-minute timetable period**.

---

## ⚙️ Session Generation

Course requirements are converted into individual teaching sessions.

The configured session generation logic is:

```text
3 Credit Hours → 3 Weekly Sessions
2 Credit Hours → 2 Weekly Sessions
1 Credit Hour  → 1 Weekly Session
Lab Row        → 1 Session
```

These individual sessions become the units scheduled by the CP-SAT solver.

---

# 🔍 Independent Post-Solution Validation

The project does not rely only on the solver result.

After timetable generation and room assignment, the final timetable is independently checked by:

```text
src/postvalidator.py
```

The validator checks:

```text
[PASS] every_session_scheduled
[PASS] no_duplicate_assignments
[PASS] no_teacher_conflict
[PASS] no_section_conflict
[PASS] no_room_conflict
[PASS] valid_days
[PASS] valid_periods
[PASS] valid_rooms
[PASS] duration_respected
[PASS] room_restrictions_respected
```

A successful result produces:

```text
RESULT: VALIDATION PASSED
```

This provides an additional verification layer between solver output and final exported results.

---

# 📁 Project Structure

```text
ai_timetable_generator/
│
├── main.py
├── requirements.txt
├── README.md
├── REVIEW_FIXES.md
├── .gitignore
│
├── data/
│   └── FSC_F26_TT_v1.0.2_06082026.xlsx
│
├── outputs/
│   ├── generated_timetable.xlsx
│   ├── generated_timetable.csv
│   ├── conflict_report.csv
│   └── validation_report.txt
│
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── models.py
│   ├── data_loader.py
│   ├── validator.py
│   ├── constraint_model.py
│   ├── solver.py
│   ├── postvalidator.py
│   ├── exporter.py
│   └── utils.py
│
└── tests/
    ├── __init__.py
    ├── test_constraints.py
    ├── test_data_loader.py
    └── test_validator.py
```

## File and Folder Responsibilities

| File / Folder                          | Purpose                                                                                                                                                     |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `main.py`                              | Main entry point of the application. Runs the complete pipeline: data loading, input validation, CP-SAT scheduling, post-validation, and output generation. |
| `requirements.txt`                     | Contains all Python libraries required to run the project.                                                                                                  |
| `README.md`                            | Project documentation explaining the problem, approach, constraints, installation, usage, and results.                                                      |
| `REVIEW_FIXES.md`                      | Contains project review notes and implemented fixes/improvements.                                                                                           |
| `.gitignore`                           | Specifies files and folders that should not be uploaded to GitHub, such as virtual environments and temporary files.                                        |
| `data/`                                | Contains the provided input Excel workbook used for timetable generation.                                                                                   |
| `data/FSC_F26_TT_v1.0.2_06082026.xlsx` | Main input dataset containing courses, teachers, sections, timetable information, periods, and rooms.                                                       |
| `outputs/`                             | Stores all files generated by the application.                                                                                                              |
| `outputs/generated_timetable.xlsx`     | Final generated timetable in Excel format.                                                                                                                  |
| `outputs/generated_timetable.csv`      | Final generated timetable in CSV format.                                                                                                                    |
| `outputs/conflict_report.csv`          | Reports conflicts or issues detected during analysis of the input timetable.                                                                                |
| `outputs/validation_report.txt`        | Contains solver information and final independent validation results.                                                                                       |
| `src/`                                 | Contains the main source code and application logic.                                                                                                        |
| `src/__init__.py`                      | Marks the `src` directory as a Python package.                                                                                                              |
| `src/config.py`                        | Stores project configuration such as file paths, valid days, active periods, solver settings, penalties, and other constants.                               |
| `src/models.py`                        | Defines the core data structures and models used to represent timetable data, sessions, assignments, and results.                                           |
| `src/data_loader.py`                   | Reads the Excel workbook, cleans and normalizes the data, expands combined sections, and creates scheduling sessions.                                       |
| `src/validator.py`                     | Performs Stage 1 validation by analyzing the input timetable and detecting existing conflicts or data issues.                                               |
| `src/constraint_model.py`              | Builds the CP-SAT optimization model and defines the hard constraints and soft optimization objectives.                                                     |
| `src/solver.py`                        | Executes the CP-SAT solver, manages the solving process, and extracts timetable assignments from the solution.                                              |
| `src/postvalidator.py`                 | Independently validates the generated timetable after solving and checks all required constraints.                                                          |
| `src/exporter.py`                      | Creates and exports the final Excel timetable, CSV file, conflict report, and validation report.                                                            |
| `src/utils.py`                         | Contains shared helper functions and utilities, including logging and reusable support functions.                                                           |
| `tests/`                               | Contains automated tests for important project components.                                                                                                  |
| `tests/__init__.py`                    | Marks the tests directory as a Python package.                                                                                                              |
| `tests/test_constraints.py`            | Tests constraint-related behavior and verifies that important scheduling rules are enforced correctly.                                                      |
| `tests/test_data_loader.py`            | Tests Excel loading, preprocessing, normalization, and section expansion logic.                                                                             |
| `tests/test_validator.py`              | Tests input validation and conflict detection logic.                                                                                                        |

---

# ⚙️ Requirements

Install the project dependencies using:

```bash
python -m pip install -r requirements.txt
```

Main libraries:

* `pandas`
* `openpyxl`
* `ortools`
* `pytest`

---

# 🚀 How to Run the Project

## 1. Clone the Repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
```

## 2. Move into the Project Folder

```bash
cd ai_timetable_generator
```

## 3. Install Dependencies

```bash
python -m pip install -r requirements.txt
```

## 4. Run the Application

```bash
python main.py
```

The complete process is:

```text
Load Excel Data
      ↓
Input Analysis & Validation
      ↓
CP-SAT Timetable Generation
      ↓
Room Assignment
      ↓
Independent Validation
      ↓
Export Results
```

---

# 🧪 Running Tests

Run all automated tests using:

```bash
python -m pytest -q
```

The tests cover important functionality including:

* Constraint behavior
* Data loading
* Data preprocessing
* Section expansion
* Input validation
* Conflict detection
* Scheduling correctness

---

# 📤 Generated Outputs

After successfully running the project, output files are created inside:

```text
outputs/
```

### `generated_timetable.xlsx`

The main final timetable in Excel format.

### `generated_timetable.csv`

The final timetable in CSV format.

### `conflict_report.csv`

Contains conflicts and data issues detected during input analysis.

### `validation_report.txt`

Contains information such as:

* Solver status
* Objective value
* Solver execution time
* Number of search branches
* Number of solver conflicts
* Total scheduled sessions
* Independent validation results

---

# 📊 Results

The project was tested on the supplied timetable workload.

### Scheduling Result

```text
1,121 / 1,121 sessions scheduled
```

### Independent Validation

The generated timetable passed the following checks:

```text
[PASS] every_session_scheduled
[PASS] no_duplicate_assignments
[PASS] no_teacher_conflict
[PASS] no_section_conflict
[PASS] no_room_conflict
[PASS] valid_days
[PASS] valid_periods
[PASS] valid_rooms
[PASS] duration_respected
[PASS] room_restrictions_respected
```

Final result:

```text
RESULT: VALIDATION PASSED
```

---

## Solver Status

Depending on the machine, configuration, and solver time limit, the solver may return:

### `OPTIMAL`

A valid solution was found and the solver proved that no better solution exists for the configured optimization objective.

### `FEASIBLE`

A valid solution satisfying all hard constraints was found, but optimality was not proven within the configured search limit.

In both cases, the final timetable is independently validated before it is accepted.

---

# 🔄 Alternative Approaches Considered

| Approach                     | Main Strength                         | Main Limitation                             |
| ---------------------------- | ------------------------------------- | ------------------------------------------- |
| Rule-Based                   | Simple implementation                 | Difficult to scale                          |
| Greedy Algorithm             | Fast                                  | Local decisions can create future conflicts |
| Traditional Machine Learning | Learns historical patterns            | Cannot guarantee hard constraints           |
| Genetic Algorithm            | Flexible optimization                 | Requires fitness and repair mechanisms      |
| Simulated Annealing          | Good search capability                | No inherent feasibility guarantee           |
| Integer Programming / MIP    | Strong mathematical formulation       | Can create very large models                |
| Reinforcement Learning       | Can learn scheduling strategies       | Requires training and reward design         |
| **Google OR-Tools CP-SAT**   | **Direct constraints + optimization** | **Requires careful model design**           |

---

# 🥇 Why Google OR-Tools CP-SAT?

Google OR-Tools CP-SAT was selected because timetable generation is fundamentally a **constraint satisfaction and optimization problem**.

It provides:

* Direct modeling of hard constraints.
* Strong support for scheduling problems.
* Optimization of soft objectives.
* No requirement for historical training data.
* Good performance on discrete combinatorial problems.
* Explainable scheduling logic.
* Support for large constraint-based search spaces.

The main difference is:

```text
Traditional Machine Learning
        ↓
Learn From Historical Data
        ↓
Predict an Output
```

While this project requires:

```text
Constraints + Requirements
        ↓
Search for a Valid Combination
        ↓
Optimize Timetable Quality
```

Therefore, CP-SAT is a more suitable solution than traditional Machine Learning for this task.
---
# 🔮 Future Improvements

Possible improvements include:

* Teacher-specific availability
* Teacher preferred time slots
* Maximum classes per teacher per day
* Maximum consecutive classes
* Room capacity constraints
* More detailed lab-room eligibility
* Student capacity constraints
* Web interface for Excel upload
* Interactive timetable visualization
* Manual timetable adjustment
* Comparison of multiple optimization approaches

---

# 👨‍💻 Author

**Zarmina Khalid**

AI/ML Engineer

**Python | Machine Learning | NLP | Optimization | AI Systems**

---

# 🏁 Conclusion

This project demonstrates an AI-assisted solution to a real-world academic scheduling problem using **Constraint Programming and Combinatorial Optimization**.

The system:

* Reads timetable data from Excel.
* Processes teachers, courses, sections, periods, and rooms.
* Converts course requirements into individual sessions.
* Uses Google OR-Tools CP-SAT to optimize session scheduling.
* Prevents teacher conflicts.
* Prevents section conflicts.
* Assigns rooms without conflicts.
* Performs independent post-solution validation.
* Generates Excel, CSV, conflict, and validation reports.
* Includes automated tests for important project components.

## Final Result

```text
1,121 / 1,121 sessions successfully scheduled
10 / 10 independent validation checks passed
RESULT: VALIDATION PASSED
```
