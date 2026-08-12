# 🎓 AI-Assisted Timetable Generator

An AI-assisted academic timetable generation and optimization system built using **Python** and **Google OR-Tools CP-SAT**.

The system reads an Excel workbook and automatically generates a valid timetable while handling teacher conflicts, section conflicts, room conflicts, valid time slots, and required teaching sessions.

---

## 🎯 Problem Statement

Creating an academic timetable manually is difficult because multiple constraints must be satisfied at the same time.

The system ensures that:

* A teacher is not assigned to two classes at the same time.
* A section does not have two subjects at the same time.
* Every required session is scheduled.
* Only valid days and time periods are used.
* A room is not assigned to multiple classes simultaneously.
* Valid rooms and room restrictions are respected.
* Timetable quality is improved by reducing unnecessary gaps and late periods.

This problem is treated as a **Constraint Satisfaction and Combinatorial Optimization Problem**.

---

## 🧠 Approach

This project uses **Google OR-Tools CP-SAT**.

Traditional Machine Learning is mainly used to learn patterns from historical data and predict outputs. However, timetable generation requires finding a combination of assignments that satisfies strict rules and constraints.

Therefore, CP-SAT is a better approach because it can directly model scheduling constraints and optimize the final solution.

### Workflow

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

## 🏗️ Two-Phase Scheduling

### Phase 1 — CP-SAT Optimization

CP-SAT assigns:

```text
Session → Day + Period
```

It handles:

* Teacher conflicts
* Section conflicts
* Combined sections
* Valid days and periods
* Required session scheduling
* Existing timetable preferences
* Teacher gap reduction
* Section gap reduction
* Late-period penalties

### Phase 2 — Room Assignment

After CP-SAT determines the day and period, rooms are assigned deterministically.

More restricted courses, including lab courses, are prioritized.

The final timetable is then independently validated for room conflicts and room restrictions.

This approach reduces model complexity compared to directly solving:

```text
Session × Day × Period × Room
```

for every session.

---

## 🔒 Constraints

### Hard Constraints

The following constraints must never be violated:

1. Every required session must be scheduled.
2. A teacher cannot teach two classes at the same time.
3. A section cannot attend two classes at the same time.
4. Only valid days can be used.
5. Only valid periods can be used.
6. A room cannot contain multiple classes at the same time.
7. Assigned rooms must be valid rooms from the dataset.
8. Combined sections are handled correctly.
9. Session duration must match the configured timetable period.
10. Room restrictions must be respected.

### Soft Constraints

After satisfying hard constraints, the system attempts to improve timetable quality by:

* Reducing unnecessary teacher gaps.
* Reducing unnecessary section gaps.
* Reducing late-period usage.
* Preserving valid existing timetable placements where possible.

---

## 📂 Input Data

The project uses the provided Excel workbook:

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

* Teachers
* Courses
* Sections
* Programs
* Credit hours
* Course categories
* Existing timetable placements
* Days
* Time periods
* Rooms

---

## 📅 Scheduling Configuration

### Available Days

```text
Mon
Tue
Wed
Thu
Fri
Sat
```

### Active Time Periods

```text
08:30-10:00
10:00-11:30
11:30-13:00
13:00-14:30
14:30-16:00
16:00-17:30
17:30-19:00
```

Each session occupies one configured **90-minute period**.

### Session Generation

The project converts course requirements into individual sessions.

```text
3 Credit Hours → 3 Weekly Sessions
2 Credit Hours → 2 Weekly Sessions
1 Credit Hour  → 1 Weekly Session
Lab Row        → 1 Session
```

These sessions become the scheduling units used by the CP-SAT solver.

---

## 🔍 Independent Validation

The final timetable is not accepted without independent validation.

After generation, `src/postvalidator.py` checks:

* Every session is scheduled
* No duplicate assignments
* No teacher conflicts
* No section conflicts
* No room conflicts
* Valid days
* Valid periods
* Valid rooms
* Session duration
* Room restrictions

Successful output:

```text
RESULT: VALIDATION PASSED
```

---

## 📁 Project Structure

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

---

## ⚙️ Requirements

Install the required libraries:

```bash
python -m pip install -r requirements.txt
```

Main dependencies:

* pandas
* openpyxl
* ortools
* pytest

---

## 🚀 How to Run

### 1. Clone the Repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
```

### 2. Move into the Project Folder

```bash
cd ai_timetable_generator
```

### 3. Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Run the Project

```bash
python main.py
```

The complete workflow will:

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

## 🧪 Run Tests

Run the automated tests using:

```bash
python -m pytest -q
```

The project includes tests for:

* Constraint behavior
* Data loading
* Section expansion
* Validation logic
* Scheduling correctness

---

## 📤 Generated Outputs

After running the project, the following files are generated inside the `outputs/` folder:

### `generated_timetable.xlsx`

Final timetable in Excel format.

### `generated_timetable.csv`

Final timetable in CSV format.

### `conflict_report.csv`

Reports conflicts and issues found during input analysis.

### `validation_report.txt`

Contains information about:

* Solver status
* Objective value
* Solver time
* Number of branches
* Number of conflicts
* Total scheduled sessions
* Independent validation results

---

## 📊 Results

The project was tested on the supplied timetable workload.

```text
1,121 / 1,121 sessions scheduled
```

The final timetable passed independent validation checks for:

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

The solver may return:

* **OPTIMAL** — A solution was found and the best result was proven for the configured objective.
* **FEASIBLE** — A valid solution satisfying the hard constraints was found, but optimality was not proven within the configured time limit.

In both cases, the final timetable is independently validated.

---

## 🔄 Alternative Approaches Considered

| Approach                     | Main Limitation                                       |
| ---------------------------- | ----------------------------------------------------- |
| Rule-Based                   | Difficult to scale for complex constraints            |
| Greedy Algorithm             | Early decisions may cause future conflicts            |
| Traditional Machine Learning | Cannot guarantee hard constraints                     |
| Genetic Algorithm            | Requires fitness functions and repair mechanisms      |
| Simulated Annealing          | Does not inherently guarantee feasibility             |
| Integer Programming / MIP    | Can create very large optimization models             |
| Reinforcement Learning       | Requires training and reward design                   |
| **Google OR-Tools CP-SAT**   | **Selected for constraint handling and optimization** |

---

## 🥇 Why Google OR-Tools CP-SAT?

CP-SAT was selected because it provides:

* Direct hard-constraint modeling
* Strong scheduling and optimization capabilities
* Support for soft optimization objectives
* No need for historical training data
* Good performance for discrete scheduling problems
* Explainable scheduling logic
* Scalability for large combinatorial problems

The key difference is:

```text
Traditional Machine Learning
        ↓
Predict an Output
```

while:

```text
CP-SAT
        ↓
Find a Valid Solution
        +
Optimize the Solution
```

Therefore, CP-SAT is more suitable for this timetable generation task.

---

## 🔮 Future Improvements

Possible future improvements include:

* Teacher-specific availability
* Teacher preferred time slots
* Maximum classes per teacher per day
* Maximum consecutive classes
* Room capacity constraints
* More detailed lab-room eligibility
* Web interface for Excel upload
* Interactive timetable visualization
* Manual timetable adjustment
* Comparison of different optimization approaches

---

## 👨‍💻 Author

**Hafiz Talha**

AI/ML Engineer

**Python | Machine Learning | NLP | Optimization | AI Systems**

---

## 🏁 Conclusion

This project demonstrates an AI-assisted approach to solving a real-world academic scheduling problem using **Constraint Programming and Combinatorial Optimization**.

The system:

* Reads timetable data from Excel.
* Processes teachers, courses, sections, periods, and rooms.
* Generates individual teaching sessions.
* Uses Google OR-Tools CP-SAT for timetable optimization.
* Prevents teacher and section conflicts.
* Assigns rooms without conflicts.
* Validates the final solution independently.
* Generates Excel, CSV, and validation reports.

**Final Result: 1,121 / 1,121 sessions successfully scheduled with all independent validation checks passed.**
