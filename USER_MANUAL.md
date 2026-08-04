# 📚 Timetable Scheduling System - User Manual

**Version:** 2.0  
**Last Updated:** August 2026  
**Application:** School/College Class Timetable Generator  
**Status:** Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Step-by-Step Guide](#step-by-step-guide)
4. [Features Explained](#features-explained)
5. [Advanced Options](#advanced-options)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)
8. [Limitations & Constraints](#limitations--constraints)
9. [FAQ](#faq)

---

## Overview

### What is this tool?

This is an **automated class timetable generator** for schools and colleges. It uses advanced constraint-solving algorithms (Google OR-Tools) to create conflict-free weekly timetables for multiple classes, with support for:

- ✅ Multiple classes (CSE, ECE, Mechanical, Civil, etc.)
- ✅ Theory subjects + practical labs
- ✅ Teacher availability tracking
- ✅ Multi-period lab blocks (consecutive slots)
- ✅ Split subjects across multiple teachers
- ✅ PDF & Excel export

### Who should use this?

- **Academic coordinators** managing class schedules
- **Department heads** coordinating multiple branches
- **Timetable committees** in educational institutions
- **Anyone** avoiding manual timetable conflicts

---

## Getting Started

### Accessing the Application

**URL:** `https://your-school-timetable.onrender.com` (or your hosted domain)

**Browser Support:** Chrome, Firefox, Safari, Edge (latest versions)

**No login required** — each browser session is private and isolated.

### What You'll Need

1. **Course list** — subjects, hours, teacher names
2. **School calendar** — days per week, periods per day
3. **Lab details** — which subjects are labs, how many consecutive periods needed
4. **Teacher names** — consistency is important (exact spelling/abbreviations)

---

## Step-by-Step Guide

### Step 1: Prepare Your Data

Before uploading, organize your course information in **one of these formats:**

#### Option A: XML File (Recommended for complex schedules)

Create a `.xml` file with this structure:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<timetable>
  <config>
    <days>5</days>
    <periods>6</periods>
  </config>
  
  <classes>
    <class name="I-CSE-A">
      <subject>
        <name>General English</name>
        <teacher>Dr. Smith</teacher>
        <hours>3</hours>
        <type>theory</type>
      </subject>
      
      <subject>
        <name>C Programming Lab</name>
        <teacher>Dr. Johnson</teacher>
        <hours>6</hours>
        <type>lab</type>
        <periods>2</periods>
      </subject>
    </class>
  </classes>
</timetable>
```

**Key fields:**
- `<days>` — weekdays (5 = Mon-Fri, 6 = Mon-Sat)
- `<periods>` — periods per day (typically 6-8)
- `<type>` — `theory` or `lab`
- `<periods>` (labs only) — consecutive periods per lab block (usually 1-2)

#### Option B: PDF (extracted automatically using AI)

Provide a scanned course list PDF. The system will try to extract teacher names and hours automatically.

⚠️ **Note:** PDF extraction requires API access and may need manual review.

---

### Step 2: Upload Your Data

1. **Go to home page** → Click "Upload PDF or XML"
2. **Select file** → Choose your `.xml` or `.pdf` file
3. **Click upload** → Wait for processing (10-30 seconds)
4. **Review results** → System shows extracted data

---

### Step 3: Configure School Week Structure

After upload, you'll see a data review page with:

**📊 Basic Config:**
- **Working Days:** Select 5 (Mon-Fri) or 6 (Mon-Sat)
- **Periods per Day:** Typically 6 or 8
- **Lab Rooms:** Number of available lab spaces (affects concurrent lab scheduling)

**Example:**
```
Working Days: 6 (Monday to Saturday)
Periods per Day: 6
Total Weekly Slots: 36 (6 × 6)
Total Lab Rooms: 2
```

---

### Step 4: Handle Split Subjects (Optional)

If a subject has multiple teacher options (e.g., "II Language" can be Telugu, Sanskrit, or Hindi):

1. **Find the subject row** in the table
2. **Set Type → 🔀 Split**
3. **Name the block** (e.g., "II Language")
4. **Set hours** (e.g., 3 hours)
5. **Add sub-options:**
   - Row 1: General II Language (Telugu teacher) - no teacher here, just sub-option name
   - Row 2: General II Language (Sanskrit teacher) - no teacher here, just sub-option name
   - Row 3: General II Language (Hindi teacher) - no teacher here, just sub-option name

When a class is assigned a "II Language" slot, it picks one sub-option (one teacher).

---

### Step 5: Generate Timetable

1. **Click "Generate Timetable"** button
2. **Wait for solver** — typically 5-30 seconds depending on complexity
   - Small (4 classes): ~5 seconds
   - Medium (10 classes): ~15 seconds
   - Large (20 classes): ~60 seconds
3. **View results** — timetable grid appears for each class

**✅ What success looks like:**
- No teacher teaches 2 classes at the same time
- All labs are placed in consecutive periods
- Each subject gets all requested hours

---

### Step 6: Review & Export

**Review the timetable:**
- Click each class tab to view its weekly schedule
- Check for any "Free" slots that indicate gaps
- Verify lab blocks are correctly placed

**Export options:**
1. **📊 Download as Excel** — editable spreadsheet for all classes
2. **📄 Download as PDF** — printable timetable (high quality)
3. **💾 Save Session** — bookmark this session to resume later

---

## Features Explained

### 🔀 Split Subjects (Electives/Multiple Options)

**Use case:** A class can take ONE of multiple language options.

**Example:**
```
II Language (Split Block)
├─ Telugu (Dr. S7)
├─ Sanskrit (Dr. S8)
└─ Hindi (Dr. S9)
```

Each class chooses one teacher; the system ensures they all have the same period.

**How to set up:**
1. Mark the subject as "Split" (🔀 icon)
2. Add each teacher option as a separate row
3. Use "🔗 Merge" to force all sections of the same split to run simultaneously

---

### 🔗 Merge Groups (Sync Across Classes)

**Use case:** Two classes take the same lab at the same time (shared lab space).

**Example:**
```
CSE-A: Python Lab — Dr. Chen (Period 3)
CSE-B: Python Lab — Dr. Chen (Period 3)
Both at the same time (only 1 lab room available)
```

**How to set up:**
1. Click "🔗 Merge" button
2. Select both lab rows
3. Name the group (e.g., "Python Lab Shared")
4. Apply

---

### 📌 Fixed Slots (Lock a Subject to a Specific Time)

**Use case:** Assembly happens every Monday 8 AM.

**How to set up:**
1. Find "Awareness Course" or special subject row
2. Click "📌 Fix Slot"
3. Select day and period
4. Save

Now that subject **always** appears at that exact time.

---

### ⏰ Teacher Unavailability

**Use case:** Dr. Smith is unavailable on Fridays (research day).

**Note:** Currently set in XML during upload:

```xml
<teacher_unavailability>
  <teacher name="Dr. Smith">
    <unavailable day="4" period_start="1" period_end="8"/>
  </teacher>
</teacher_unavailability>
```

The solver won't schedule this teacher on that day.

---

### 🔄 Swap Slots (Adjust After Generation)

**Use case:** Move "Physics" from Tuesday P3 to Thursday P4.

**How to use:**
1. View the generated timetable
2. Click the "🔄 Swap" button on two cells
3. System validates (no teacher conflicts, no duplicate subjects on same day)
4. Change applies immediately

**What it checks:**
- Teacher isn't already teaching another class at target time
- Subject doesn't appear twice on same day for that class

---

## Advanced Options

### Lab Configuration

**Labs require consecutive periods.** For example:

```
Software Lab: 6 hours
Periods per block: 2 (consecutive)
= 3 separate 2-hour sessions across the week
```

Each session must occupy 2 consecutive periods (P1-P2, or P3-P4, etc.).

**Best practice:** For a 6-hour lab, set periods to 2 (gives you 3 sessions × 2 hours).

### Handling Over-Constrained Problems

If the solver says **"INFEASIBLE"** (can't find a valid timetable):

**Possible causes:**
1. Too many classes for available slots
2. A teacher assigned to too many hours
3. Lab blocks don't fit in consecutive free slots
4. Conflicting fixed slots

**Solutions:**
1. Add more periods per day (e.g., 6 → 8)
2. Add more working days (e.g., 5 → 6)
3. Split high-load teachers across multiple instructors
4. Reduce lab block sizes
5. Remove fixed slot constraints (make flexible)

---

## Troubleshooting

### Problem: "No data found. Please upload a PDF first."

**Cause:** No timetable data in current session.

**Solution:**
1. Upload XML/PDF file
2. Wait for extraction (spinning loader)
3. Review extracted data on next page

---

### Problem: Solver returns "INFEASIBLE"

**Cause:** The problem has no valid solution under current constraints.

**Solution:**
1. **Check workload distribution:**
   ```
   Total hours per class ÷ (days × periods) = utilization
   
   Example: 30 hours ÷ (5 days × 6 periods = 30 slots) = 100% full
   → Add more periods or days
   ```

2. **Check teacher availability:**
   - Is one teacher assigned to too many classes?
   - Do unavailable days block critical slots?

3. **Reduce constraints:**
   - Remove fixed slots (make them flexible)
   - Remove merge groups temporarily
   - Remove unavailability restrictions

4. **Increase capacity:**
   - Add a 6th working day (Mon-Sat instead of Mon-Fri)
   - Add 2 more periods per day (6 → 8)

---

### Problem: Export to PDF/Excel fails

**Cause:** Session data corrupted or incomplete.

**Solution:**
1. Try generating timetable again
2. If error persists, save the XML/JSON file
3. Upload again in a new session
4. Try export once more

---

### Problem: Solver takes too long (>2 minutes)

**Cause:** Problem is very complex (20+ classes, many constraints).

**Solution:**
1. **Be patient** — Large problems can take 30-60 seconds
2. **Simplify constraints:**
   - Remove non-critical fixed slots
   - Remove split subject options
3. **Upgrade server** (if self-hosted) — better CPU helps significantly

---

### Problem: Lab blocks not consecutive

**Cause:** Not enough consecutive free slots for the lab.

**Solution:**
1. Check current timetable for conflicts
2. Reduce lab block size (e.g., 2-period blocks instead of 3)
3. Add more free periods in the week
4. Reduce total lab hours if possible

---

### Problem: Teacher appears in two classes same time

**Cause:** Data entry error (teacher name misspelled or duplicated).

**Solution:**
1. **Consistency check:** Teacher names must be exactly the same everywhere
   - ❌ "Dr. Smith" vs "Dr. S. Smith" vs "smith"
   - ✅ Use "Dr. Smith" consistently

2. **XML validation:**
   ```xml
   <!-- WRONG - inconsistent names -->
   <teacher>Dr. Smith</teacher>
   <teacher>Dr. S. Smith</teacher>
   
   <!-- CORRECT - consistent -->
   <teacher>Dr. Smith</teacher>
   <teacher>Dr. Smith</teacher>
   ```

3. **Re-upload corrected file**

---

## Best Practices

### 1. Naming Conventions

**Teachers:**
```
✅ Good:     Dr. Smith, Dr. Johnson, Dr. Patel
❌ Bad:      smith, S.smith, dr smith, Dr smith
```

**Classes:**
```
✅ Good:     I-CSE-A, II-ECE-B, III-MECH-A
❌ Bad:      CSE1, ECE2, Class A
```

**Subjects:**
```
✅ Good:     General English, Problem Solving with Computers
❌ Bad:      English, PS Computers, Eng
```

### 2. Data Validation Before Upload

1. **Count total hours:**
   ```
   Sum all subject hours for each class
   Should be achievable in (days × periods) slots
   ```

2. **Check teacher availability:**
   - No teacher should teach more hours than available slots
   - Example: 1 teacher teaching 20 hours in a 5-day, 6-period week = only 30 slots total

3. **Verify lab configuration:**
   - Each lab needs space for its block size
   - 6-hour lab with 2-period blocks = needs 3 × 2-period gaps throughout the week

### 3. Iterative Refinement

If first attempt is infeasible:

1. **Simplify first:** Remove optional constraints
2. **Generate:** See if basic timetable works
3. **Add back:** Gradually re-add constraints
4. **Optimize:** Once feasible, refine for quality

### 4. Export & Share Workflow

```
1. Generate timetable
2. Review in browser (check for obvious issues)
3. Export to Excel (editable for manual tweaks)
4. Export to PDF (print-friendly, share with students)
5. Save session JSON (bookmark for future reference)
```

### 5. Handling Teacher Load

**Distribute evenly:**
```
Wrong:  Dr. A teaches CSE-A, CSE-B, ECE-A (15 hours)
        Dr. B teaches MECH-A (3 hours)

Better: Dr. A teaches CSE-A, CSE-B (10 hours)
        Dr. B teaches ECE-A, MECH-A (8 hours)
        Dr. C teaches other sections (8 hours)
```

---

## Limitations & Constraints

### What This System DOES

✅ Generate conflict-free weekly timetables  
✅ Schedule multiple classes simultaneously  
✅ Support theory + lab mix  
✅ Handle teacher conflicts  
✅ Place labs in consecutive periods  
✅ Export to PDF/Excel  

### What This System DOES NOT

❌ **No student tracking** — Doesn't know which students take which courses  
❌ **No room allocation** — Doesn't assign specific classrooms/labs  
❌ **No soft constraints** — Can't optimize for "prefer morning classes"  
❌ **No multi-week scheduling** — Only generates one week at a time  
❌ **No historical data** — Previous timetables not stored automatically  
❌ **No user authentication** — Anyone with URL can access/edit  

### Solver Limitations

| Factor | Limit | Notes |
|--------|-------|-------|
| Classes | 20+ | May timeout (>60 seconds) |
| Teachers | 100+ | No hard limit, but affects solver speed |
| Subjects/class | 10+ | More subjects = longer solve time |
| Days | 5-7 | Typical school week |
| Periods/day | 6-10 | Typical school periods |
| Concurrent labs | 2-3 | Number of lab rooms available |

**Solver timeout:** If solver takes >60 seconds, it returns "INFEASIBLE" even if a solution might exist (it just needs more time).

---

## FAQ

### Q: Can I share this timetable with students?

**A:** Yes! Download the PDF and distribute digitally or print. Each class gets its own timetable showing what period each subject occurs.

---

### Q: What if two teachers want the same period?

**A:** That's a teacher conflict. The solver prevents this automatically — if both teachers are assigned to teach their respective classes at the same time, it's impossible. You must either:
- Add more periods to the day
- Add another day (6-day week)
- Assign another teacher for one of the subjects

---

### Q: Can I modify the timetable after it's generated?

**A:** Yes, use the **🔄 Swap Slots** feature to move a subject to a different time. The system will validate your swap for conflicts.

For major changes, re-upload and regenerate.

---

### Q: How long does scheduling typically take?

**A:** 
- Small (4 classes, 30 subjects): ~5 seconds
- Medium (10 classes, 80 subjects): ~20 seconds
- Large (20 classes, 160 subjects): ~60 seconds

If it takes >60 seconds, the solver times out and returns an error.

---

### Q: Can teachers request specific unavailable times?

**A:** Yes, but only in the XML file (during setup). Unavailable times are fixed constraints and don't change after upload. To modify:
1. Update the XML file
2. Re-upload
3. Regenerate

---

### Q: What format should the XML file be?

**A:** See **Step 1: Prepare Your Data** above. Critical elements:
```xml
<timetable>
  <config>
    <days>5</days>
    <periods>6</periods>
  </config>
  <classes>
    <class name="I-CSE-A">
      <subject>
        <name>Subject</name>
        <teacher>Name</teacher>
        <hours>3</hours>
        <type>theory</type>
      </subject>
    </class>
  </classes>
</timetable>
```

All XML must be **well-formed** (valid syntax). Use an XML validator if unsure.

---

### Q: Can I schedule only one class?

**A:** Yes, but the system is optimized for multi-class scheduling. For one class, just add one `<class>` block in your XML.

---

### Q: Is my data saved?

**A:** 
- **Current session:** Yes, saved in browser (clears if you close/reload)
- **Between sessions:** No, not automatically saved
- **Manual save:** Click "💾 Save Session" to download JSON file

If you want to resume later, download the JSON and re-upload it.

---

### Q: What if the PDF extraction is wrong?

**A:** Review the extracted data on the review page:
1. Correct any errors in the table
2. Continue to scheduling
3. If many errors, download as JSON, edit manually, re-upload

---

### Q: Can multiple users use this simultaneously?

**A:** Yes, each browser session is isolated. Two people can upload different data at the same time without interference.

---

### Q: Is there a mobile app?

**A:** Not yet. Use a desktop/tablet browser for best experience. Mobile support planned for v3.0.

---

## Support & Feedback

**Issues?** Check the [Troubleshooting](#troubleshooting) section above.

**Feature requests?** Email: `support@your-institution.edu`

**Report bugs?** Provide:
1. Your XML/PDF file (anonymized)
2. Error message (screenshot)
3. Steps to reproduce

---

## Version History

**v2.0 (August 2026)** — Production release
- ✅ Session isolation fixed
- ✅ Lab scheduling validation
- ✅ Teacher conflict locking
- ✅ Sub-teacher handling
- ✅ PDF/Excel export

**v1.0 (July 2026)** — Initial release

---

**Last Updated:** August 1, 2026  
**Maintained by:** Academic Coordination Team  
**Questions?** Contact the IT Help Desk
