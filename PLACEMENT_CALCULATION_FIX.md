# Placement Calculation Discrepancy - Analysis & Fix

## Problem Identified
- **Dashboard** showed: **52 placed students**
- **Placement Statistics** showed: **55 placed students**
- **Discrepancy**: 3 students

## Root Cause Analysis

### How CSVs are Logged
The system uses `data/Master_Placement_Fila.csv` which contains placement records with the following structure:
- `record_id`: Unique identifier for each record
- `company_id`: Company identifier (e.g., CMP01, CMP02)
- `company_name`: Name of the company
- `status`: Status of the placement (Completed, On-going, On-Hold, Cancelled)
- `student_names`: Comma-separated list of student names
- Other fields: campus_type, pr_assigned, role, package, etc.

### How Calculations Were Done (BEFORE FIX)

#### Dashboard (`/` route - lines 515-626)
```python
# Filter only completed company records for dashboard metrics
completed_mask = status_series.astype(str).str.strip().str.lower() == 'completed'
completed_placements = placements[completed_mask].copy()

# Get unique placed students
placed_students = set()
for names in completed_placements['student_names'].dropna():
    if names and names != '':
        placed_students.update([n.strip().upper() for n in str(names).split(',')])
```
**Result**: Only counted students from records with `status == 'completed'` → **52 students**

#### Placement Statistics (`get_comprehensive_placement_statistics()` - lines 1571-1586)
```python
# Get all placed students from Master_Placement_Fila.csv (these are "blocked")
placed_students = set()
placed_students_details = {}
for _, row in placements.iterrows():  # ← NO STATUS FILTER!
    if pd.notna(row.get('student_names')) and str(row['student_names']).strip():
        names = [n.strip().upper() for n in str(row['student_names']).split(',') if n.strip()]
        for name in names:
            placed_students.add(name)
```
**Result**: Counted students from ALL records (including On-going, On-Hold, etc.) → **55 students**

### The Discrepancy Source
Found in `data/Master_Placement_Fila.csv`:
- **Line 46**: `CMP24,Akasha Air,On-going,3.0,"ADITYA GUJAR, ANJANEY MITRA, PRATHAM JAIN"`
  - Status: **On-going** (not Completed)
  - Students: 3 students listed
  - These 3 students were counted in Placement Statistics but NOT in Dashboard

**Calculation**:
- Dashboard: 52 students (only from Completed records)
- Placement Statistics: 55 students (52 from Completed + 3 from On-going)
- **Difference**: 55 - 52 = **3 students** ✓

## Fix Applied

### Principle
**A student should only be considered "placed" if they are in a record with `status == 'completed'`**

This ensures consistency across all views:
- Dashboard
- Placement Statistics
- Students List
- PR Dashboard
- Search API

### Changes Made

1. **Placement Statistics** (`get_comprehensive_placement_statistics()` - line 1571)
   - Added status filter: `if status != 'completed': continue`
   - Now only counts students from completed records

2. **Students List** (`/students` route - line 634)
   - Added status filter when building placement mapping
   - Students are only marked as "Placed" if in completed records

3. **Search API** (`/api/search_students` - line 1116)
   - Added status filter when checking if students are placed
   - Search results now correctly show placement status

4. **PR Dashboard** (`/pr_dashboard` route - line 680)
   - Added status filter when counting placed students
   - Added status filter when calculating average package
   - PR statistics now only include completed placements

## After Fix

Both Dashboard and Placement Statistics now show: **52 placed students**

All views are now consistent:
- ✅ Dashboard: 52 placed
- ✅ Placement Statistics: 52 placed
- ✅ Students List: Only shows students from completed records as "Placed"
- ✅ PR Dashboard: Only counts students from completed records
- ✅ Search API: Correctly identifies placed students

## Data Flow Summary

```
Master_Placement_Fila.csv
    ↓
load_placements() → DataFrame
    ↓
Filter by status == 'completed'  ← KEY FIX
    ↓
Extract student_names
    ↓
Count unique students (uppercase normalized)
    ↓
Display in Dashboard/Statistics
```

## Testing Recommendations

1. Verify Dashboard shows 52 placed students
2. Verify Placement Statistics shows 52 placed students
3. Check that students in On-going records are NOT marked as "Placed" in Students List
4. Verify PR Dashboard counts match Dashboard
5. Test search API - students in On-going records should show `is_placed: false`

## Notes

- Records with status "On-going", "On-Hold", or "Cancelled" may have student names, but these students are NOT considered "placed" until the record status is changed to "Completed"
- When a record status changes from "On-going" to "Completed", those students will automatically appear in placement counts
- This ensures data integrity and prevents premature counting of placements

