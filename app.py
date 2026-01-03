from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import pandas as pd
import os
from functools import wraps, lru_cache
import json

app = Flask(__name__)
app.secret_key = 'placement_secret_key_2024'

# File paths
STUDENTS_CSV = 'data/FULL NAME LIST.csv'
PLACEMENT_CSV = 'data/Master_Placement_Fila.csv'
ANALYSIS_CSV = 'data/Analysis - Overall.csv'
ANALYSIS_FOLDER = 'data/ANALYSIS'

# Hardcoded credentials with roles
USERS = {
    'admin': {
        'password': 'admin123',
        'role': 'admin'
    },
    'user1': {
        'password': 'user123',
        'role': 'viewer'
    }
}

# PR Mapping
PR_MAPPING = {
    'PR01': 'PARICHOY NANDI',
    'PR02': 'SULEKHA K R',
    'PR03': 'KEZYA STEFFYN S',
    'PR04': 'SAMDENNIS M',
    'PR05': 'ANSON THOMAS',
    'PR06': 'JAIBY MARIYA JOSEPH',
    'PR07': 'JESVIN K JUSTIN',
    'PR08': 'NITISH CHURIWALA',
    'PR09': 'VIDYA SHREE B V',
    'PR10': 'KISHAN KUMAR',
    'PR11': 'KUSUMA H K',
    'PR12': 'MARIA BOBY'
}

# Class assignment based on Sl. no
def get_class_from_slno(sl_no):
    sl_no = int(sl_no)
    if 1 <= sl_no <= 59:
        return 'MCA A'
    elif 60 <= sl_no <= 119:
        return 'MCA B'
    elif 120 <= sl_no <= 176:
        return 'MSc AIML'
    return 'Unknown'

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin only decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Load CSV files
def load_students():
    df = pd.read_csv(STUDENTS_CSV)
    df.columns = df.columns.str.strip()
    df['Name'] = df['Name'].str.strip()
    df['Class'] = df['Sl .no'].apply(get_class_from_slno)
    return df

def load_placements():
    df = pd.read_csv(PLACEMENT_CSV)
    df.columns = df.columns.str.strip()
    
    # Add unique record_id if it doesn't exist
    if 'record_id' not in df.columns:
        df.insert(0, 'record_id', range(1, len(df) + 1))
        save_placements(df)
    
    return df

def save_placements(df):
    df.to_csv(PLACEMENT_CSV, index=False)

# Load and parse Analysis - Overall.csv
def load_analysis_data():
    """
    Load and parse the Analysis - Overall.csv file which has a complex header structure.
    Returns a dictionary with company data and student progress information.
    """
    try:
        df = pd.read_csv(ANALYSIS_CSV, header=None)
        
        # Extract company names from row 0 (index 0)
        company_row = df.iloc[0].tolist()
        # Extract number of rounds from row 1 (index 1)
        rounds_row = df.iloc[1].tolist()
        # Extract counts from row 2 (index 2)
        counts_row = df.iloc[2].tolist()
        # Column headers from row 3 (index 3)
        headers_row = df.iloc[3].tolist()
        # Data starts from row 4 (index 4)
        data_df = df.iloc[4:].copy()
        
        # Parse company information
        companies = []
        current_company = None
        current_rounds = None
        col_start = 0
        
        for i, cell in enumerate(company_row):
            if pd.notna(cell) and 'Company Name' in str(cell):
                # Extract company name
                company_name = str(cell).replace('Company Name :', '').strip()
                # Get number of rounds
                rounds_str = str(rounds_row[i]) if i < len(rounds_row) and pd.notna(rounds_row[i]) else ''
                rounds = rounds_str.replace('Number of Rounds :', '').strip() if rounds_str else ''
                
                if current_company:
                    companies.append({
                        'name': current_company,
                        'rounds': current_rounds,
                        'start_col': col_start,
                        'end_col': i
                    })
                
                current_company = company_name
                current_rounds = rounds
                col_start = i
        
        # Add last company
        if current_company:
            companies.append({
                'name': current_company,
                'rounds': current_rounds,
                'start_col': col_start,
                'end_col': len(company_row)
            })
        
        # Set proper column names for data
        data_df.columns = headers_row
        data_df = data_df.reset_index(drop=True)
        
        return {
            'companies': companies,
            'data': data_df,
            'headers': headers_row,
            'counts': counts_row
        }
    except Exception as e:
        print(f"Error loading analysis data: {e}")
        import traceback
        traceback.print_exc()
        return None

# Match names between Analysis - Overall.csv and FULL NAME LIST.csv
def match_analysis_names():
    """
    Match student names between Analysis - Overall.csv and FULL NAME LIST.csv
    Returns matching statistics and detailed comparison.
    """
    try:
        students_df = load_students()
        analysis_data = load_analysis_data()
        
        if analysis_data is None:
            return None
        
        # Get student names from FULL NAME LIST.csv (normalized)
        full_list_names = {}
        for _, row in students_df.iterrows():
            name = str(row['Name']).strip().upper()
            full_list_names[name] = {
                'original': row['Name'],
                'reg_no': row['Reg.no'],
                'class': row['Class']
            }
        
        # Get student names from Analysis - Overall.csv
        analysis_df = analysis_data['data']
        name_col = 'Name of the Student'
        
        if name_col not in analysis_df.columns:
            return None
        
        analysis_names = {}
        matched = []
        not_matched = []
        
        for _, row in analysis_df.iterrows():
            analysis_name = str(row[name_col]).strip()
            analysis_name_upper = analysis_name.upper()
            reg_no_analysis = str(row.get('Register Number', '')).strip() if 'Register Number' in row else ''
            
            # Try exact match first
            if analysis_name_upper in full_list_names:
                matched.append({
                    'analysis_name': analysis_name,
                    'full_list_name': full_list_names[analysis_name_upper]['original'],
                    'reg_no_analysis': reg_no_analysis,
                    'reg_no_full_list': full_list_names[analysis_name_upper]['reg_no'],
                    'class': full_list_names[analysis_name_upper]['class'],
                    'match_type': 'exact'
                })
                analysis_names[analysis_name_upper] = True
            else:
                # Try fuzzy matching
                found = False
                for full_name_upper, full_info in full_list_names.items():
                    # Check if names are similar (word-based matching)
                    analysis_words = set(analysis_name_upper.split())
                    full_words = set(full_name_upper.split())
                    
                    # If most words match, consider it a match
                    if len(analysis_words) >= 2 and len(full_words) >= 2:
                        common_words = analysis_words.intersection(full_words)
                        if len(common_words) >= min(2, len(analysis_words) - 1):
                            matched.append({
                                'analysis_name': analysis_name,
                                'full_list_name': full_info['original'],
                                'reg_no_analysis': reg_no_analysis,
                                'reg_no_full_list': full_info['reg_no'],
                                'class': full_info['class'],
                                'match_type': 'fuzzy'
                            })
                            analysis_names[analysis_name_upper] = True
                            found = True
                            break
                
                if not found:
                    not_matched.append({
                        'analysis_name': analysis_name,
                        'reg_no_analysis': reg_no_analysis
                    })
                    analysis_names[analysis_name_upper] = False
        
        # Find names in FULL NAME LIST that are not in Analysis
        only_in_full_list = []
        for name_upper, info in full_list_names.items():
            if name_upper not in analysis_names:
                only_in_full_list.append({
                    'name': info['original'],
                    'reg_no': info['reg_no'],
                    'class': info['class']
                })
        
        return {
            'matched': matched,
            'not_matched': not_matched,
            'only_in_full_list': only_in_full_list,
            'stats': {
                'total_in_analysis': len(analysis_df),
                'total_in_full_list': len(students_df),
                'matched_count': len(matched),
                'not_matched_count': len(not_matched),
                'only_in_full_list_count': len(only_in_full_list),
                'match_percentage': round((len(matched) / len(analysis_df)) * 100, 2) if len(analysis_df) > 0 else 0
            },
            'analysis_data': analysis_data
        }
    except Exception as e:
        print(f"Error matching analysis names: {e}")
        import traceback
        traceback.print_exc()
        return None

# Cache for student lookups to improve performance
_student_cache = {}
_student_df_cache = None

def _load_students_cached():
    global _student_df_cache
    if _student_df_cache is None:
        _student_df_cache = load_students()
    return _student_df_cache

# Get student details by name or register number (improved function with fuzzy matching and caching)
def get_student_details(name_or_reg_no):
    # Check cache first
    search_key = name_or_reg_no.strip().upper()
    if search_key in _student_cache:
        return _student_cache[search_key]
    
    students = _load_students_cached()
    # Normalize the search term
    normalized_search = ' '.join(name_or_reg_no.strip().upper().split())
    
    # Try exact match by name first
    match = students[students['Name'].str.strip().str.upper() == normalized_search]
    if not match.empty:
        result = {
            'name': match.iloc[0]['Name'],
            'reg_no': match.iloc[0]['Reg.no'],
            'class': match.iloc[0]['Class']
        }
        _student_cache[search_key] = result
        return result
    
    # Try exact match by Register Number
    match = students[students['Reg.no'].astype(str).str.strip().str.upper() == normalized_search]
    if not match.empty:
        result = {
            'name': match.iloc[0]['Name'],
            'reg_no': match.iloc[0]['Reg.no'],
            'class': match.iloc[0]['Class']
        }
        _student_cache[search_key] = result
        return result
    
    # Try fuzzy matching by name - split names into words and match
    name_words = set(normalized_search.split())
    for idx, row in students.iterrows():
        db_name = ' '.join(str(row['Name']).strip().upper().split())
        db_words = set(db_name.split())
        
        # Check if all words from search name are in database name
        # This handles cases like "SOUJANYA BHAT" matching "SOUJANYA M BHAT"
        if name_words.issubset(db_words) or db_words.issubset(name_words):
            # Calculate similarity - more matching words = better match
            matching_words = name_words.intersection(db_words)
            if len(matching_words) >= 2 or (len(name_words) == 1 and len(matching_words) == 1):
                result = {
                    'name': row['Name'],
                    'reg_no': row['Reg.no'],
                    'class': row['Class']
                }
                _student_cache[search_key] = result
                return result
    
    # Try partial match by Register Number
    for idx, row in students.iterrows():
        reg_no = str(row['Reg.no']).strip().upper()
        if normalized_search in reg_no or reg_no in normalized_search:
            result = {
                'name': row['Name'],
                'reg_no': row['Reg.no'],
                'class': row['Class']
            }
            _student_cache[search_key] = result
            return result
    
    # Cache negative results too
    _student_cache[search_key] = None
    return None

# Get student class by name
def get_student_class(name):
    # Use the improved get_student_details function
    student_info = get_student_details(name)
    return student_info['class'] if student_info else None

def _first_non_empty(series):
    """
    Return the first non-empty string value from a pandas Series-like iterable.
    """
    for value in series:
        if pd.isna(value):
            continue
        value_str = str(value).strip()
        if value_str:
            return value_str
    return ''

def _combine_unique(series, separator=', '):
    """
    Combine unique, non-empty string values from a Series into a single string.
    """
    seen = []
    for value in series:
        if pd.isna(value):
            continue
        value_str = str(value).strip()
        if value_str and value_str not in seen:
            seen.append(value_str)
    return separator.join(seen)

def _combine_student_names(series, separator=', '):
    """
    Combine unique student names across multiple rows, ignoring case and duplicates.
    """
    seen = []
    seen_keys = set()
    for value in series:
        if pd.isna(value):
            continue
        for name in str(value).split(','):
            name_clean = name.strip()
            if not name_clean:
                continue
            key = name_clean.upper()
            if key not in seen_keys:
                seen.append(name_clean)
                seen_keys.add(key)
    return separator.join(seen)

def _normalize_status(status):
    if not status:
        return ''
    status_map = {
        'completed': 'Completed',
        'complete': 'Completed',
        'on-going': 'On-going',
        'ongoing': 'On-going',
        'on going': 'On-going',
        'cancelled': 'Cancelled',
        'canceled': 'Cancelled',
        'on-hold': 'On-Hold',
        'on hold': 'On-Hold'
    }
    normalized = status.strip().lower()
    return status_map.get(normalized, status.strip().title())

def get_unique_company_records(placements_df):
    """
    Collapse placement rows into unique company-level records based on company_id.
    """
    if placements_df.empty or 'company_id' not in placements_df.columns:
        return pd.DataFrame(columns=[
            'company_id', 'company_name', 'status', 'campus_type',
            'placement_origin', 'pr_assigned', 'pr_name',
            'role', 'package', 'student_names'
        ])
    
    normalized = placements_df.copy()
    normalized['company_id'] = normalized['company_id'].astype(str).str.strip()
    normalized = normalized[normalized['company_id'] != '']
    normalized = normalized.sort_values('record_id')
    
    records = []
    for company_id, group in normalized.groupby('company_id'):
        # Determine company status: if ANY record is "Completed", company is "Completed"
        # Priority: Completed > On-going > On-Hold > Cancelled
        statuses = group['status'].astype(str).str.strip().str.lower()
        company_status = ''
        
        if (statuses == 'completed').any():
            company_status = 'Completed'
        elif (statuses.isin(['on-going', 'ongoing', 'on going'])).any():
            company_status = 'On-going'
        elif (statuses == 'on-hold').any() or (statuses == 'on hold').any():
            company_status = 'On-Hold'
        elif (statuses == 'cancelled').any():
            company_status = 'Cancelled'
        else:
            # Fallback to first non-empty status
            company_status = _normalize_status(_first_non_empty(group.get('status', [])))
        
        pr_code = _first_non_empty(group.get('pr_assigned', []))
        pr_name = _first_non_empty(group.get('pr_name', []))
        if (not pr_name) and pr_code:
            pr_name = PR_MAPPING.get(pr_code.strip(), '')
        # Get campus_type - should be consistent within a group, but take the first non-empty
        campus_type = _first_non_empty(group.get('campus_type', []))
        # Normalize campus_type to ensure consistency
        if campus_type:
            campus_type_lower = str(campus_type).strip().lower()
            if campus_type_lower == 'on campus':
                campus_type = 'On Campus'
            elif 'off' in campus_type_lower and 'campus' in campus_type_lower:
                campus_type = 'Off Campus'
            else:
                campus_type = str(campus_type).strip()
        
        records.append({
            'company_id': company_id,
            'company_name': _first_non_empty(group.get('company_name', [])),
            'status': company_status if company_status else '',
            'campus_type': campus_type,
            'placement_origin': _first_non_empty(group.get('placement_origin', [])),
            'pr_assigned': pr_code,
            'pr_name': pr_name,
            'role': _combine_unique(group.get('role', [])),
            'package': _combine_unique(group.get('package', [])),
            'student_names': _combine_student_names(group.get('student_names', []))
        })
    return pd.DataFrame(records)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Check if user exists and password matches
        if username in USERS and USERS[username]['password'] == password:
            session['logged_in'] = True
            session['username'] = username
            session['role'] = USERS[username]['role']
            flash(f'Welcome {username}!', 'success')
            return redirect(url_for('dashboard'))
        
        flash('Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    try:
        students = load_students()
        placements = load_placements()
        
        # Filter only completed company records for dashboard metrics
        status_series = placements['status'] if 'status' in placements.columns else pd.Series([''] * len(placements), index=placements.index)
        completed_mask = status_series.astype(str).str.strip().str.lower() == 'completed'
        completed_placements = placements[completed_mask].copy()
        
        # Normalize company IDs for completed records
        if not completed_placements.empty and 'company_id' in completed_placements.columns:
            completed_placements['company_id'] = completed_placements['company_id'].astype(str).str.strip()
            completed_placements = completed_placements[completed_placements['company_id'] != '']
        
        # Ensure we always have a DataFrame to work with
        if completed_placements.empty:
            completed_placements = placements.iloc[0:0].copy()
        
        # Get unique placed students - count all students from student_names regardless of status
        placed_students = set()
        for names in placements['student_names'].dropna():
            if names and names != '':
                placed_students.update([n.strip().upper() for n in str(names).split(',')])
        
        total_students = len(students)
        total_placed = len(placed_students)
        
        company_ids = completed_placements['company_id'] if 'company_id' in completed_placements.columns else pd.Series(dtype=str)
        total_companies = company_ids.nunique()
        
        # Calculate average package
        packages = []
        for pkg in completed_placements['package'].dropna():
            pkg_str = str(pkg).strip()
            if 'LPA' in pkg_str.upper():
                try:
                    num = float(pkg_str.split()[0])
                    packages.append(num)
                except:
                    pass
        avg_package = round(sum(packages) / len(packages), 2) if packages else 0
        
        # Placement by class - optimized with caching - count all students from student_names regardless of status
        class_counts = {}
        print("Starting class count calculation...")
        for idx, row in placements.iterrows():
            if pd.notna(row.get('student_names')) and str(row.get('student_names', '')).strip():
                names = [n.strip() for n in str(row['student_names']).split(',') if n.strip()]
                for name in names:
                    try:
                        student_class = get_student_class(name)
                        if student_class:
                            class_counts[student_class] = class_counts.get(student_class, 0) + 1
                    except Exception as e:
                        print(f"Error getting class for {name}: {e}")
                        continue
        print(f"Class counts: {class_counts}")
        
        # PR stats
        pr_stats = {}
        for pr_code, pr_name in PR_MAPPING.items():
            pr_data = completed_placements[completed_placements['pr_assigned'] == pr_code]
            pr_stats[pr_name] = len(pr_data)
        
        # Top companies - count all students from student_names regardless of status
        company_student_counts = placements.groupby('company_id')['student_names'].apply(
            lambda x: sum([
                len([n.strip() for n in str(names).split(',') if n.strip()])
                for names in x.dropna() if names
            ])
        ).sort_values(ascending=False).head(10) if not placements.empty else pd.Series(dtype=float)
        
        company_name_map = placements.set_index('company_id')['company_name'].to_dict() if not placements.empty else {}
        top_companies = {
            company_name_map.get(company_id, str(company_id)): int(count)
            for company_id, count in company_student_counts.items()
        }
        
        # Campus Type Stats (On Campus vs Off Campus)
        campus_stats = {'On Campus': 0, 'Off Campus': 0}
        for campus_type in completed_placements['campus_type'].dropna():
            campus_str = str(campus_type).strip()
            if campus_str in campus_stats:
                campus_stats[campus_str] += 1
        
        # Placement Origin Stats (CPCG vs Department)
        origin_stats = {}
        for origin in completed_placements['placement_origin'].dropna():
            origin_str = str(origin).strip()
            if origin_str:
                origin_stats[origin_str] = origin_stats.get(origin_str, 0) + 1
        
        print("Dashboard data prepared successfully")
        
        return render_template('dashboard.html',
                             total_students=total_students,
                             total_placed=total_placed,
                             total_companies=total_companies,
                             avg_package=avg_package,
                             class_counts=class_counts,
                             pr_stats=pr_stats,
                             top_companies=top_companies,
                             campus_stats=campus_stats,
                             origin_stats=origin_stats)
    except Exception as e:
        print(f"Dashboard error: {e}")
        import traceback
        traceback.print_exc()
        return f"Error loading dashboard: {str(e)}", 500

@app.route('/students')
@login_required
def students():
    students_df = load_students()
    placements = load_placements()
    
    # Build placement mapping - count all students from student_names regardless of status
    placement_map = {}
    for _, row in placements.iterrows():
        if pd.notna(row['student_names']) and row['student_names']:
            names = [n.strip().upper() for n in str(row['student_names']).split(',')]
            for name in names:
                if name not in placement_map:
                    placement_map[name] = {
                        'company': row['company_name'],
                        'role': row['role'],
                        'package': row['package']
                    }
    
    students_list = []
    for _, student in students_df.iterrows():
        name_upper = student['Name'].upper()
        placement_info = placement_map.get(name_upper, {})
        students_list.append({
            'sl_no': student['Sl .no'],
            'reg_no': student['Reg.no'],
            'name': student['Name'],
            'class': student['Class'],
            'status': 'Placed' if name_upper in placement_map else 'Not Placed',
            'company': placement_info.get('company', '-'),
            'role': placement_info.get('role', '-'),
            'package': placement_info.get('package', '-')
        })
    
    return render_template('students.html', students=students_list)

@app.route('/pr_dashboard')
@login_required
def pr_dashboard():
    placements = load_placements()
    
    pr_details = {}
    for pr_code, pr_name in PR_MAPPING.items():
        pr_data = placements[placements['pr_assigned'] == pr_code]
        unique_company_records = get_unique_company_records(pr_data)
        
        # Count students - count all students from student_names regardless of status
        students_placed = set()
        for _, row in pr_data.iterrows():
            if pd.notna(row.get('student_names')) and str(row['student_names']).strip():
                names = [n.strip() for n in str(row['student_names']).split(',') if n.strip()]
                students_placed.update(names)
        
        # Calculate avg package - only from completed records
        packages = []
        for _, row in pr_data.iterrows():
            # Filter by status='completed' to be consistent with dashboard
            status = str(row.get('status', '')).strip().lower()
            if status != 'completed':
                continue  # Skip non-completed records
            
            pkg = row.get('package')
            if pd.notna(pkg):
                pkg_str = str(pkg).strip()
                if 'LPA' in pkg_str:
                    try:
                        packages.append(float(pkg_str.split()[0]))
                    except:
                        pass
        
        status_counts = {}
        for status in unique_company_records.get('status', []):
            status_str = str(status).strip() or 'Unknown'
            status_counts[status_str] = status_counts.get(status_str, 0) + 1
        
        companies_list = []
        if not unique_company_records.empty:
            companies_list = [
                {
                    'company_id': row.get('company_id', ''),
                    'name': row.get('company_name', 'N/A'),
                    'status': row.get('status', 'Unknown')
                }
                for _, row in unique_company_records.fillna('').iterrows()
            ]
        
        pr_details[pr_name] = {
            'code': pr_code,
            'drives': len(pr_data),
            'companies_count': len(companies_list),
            'students': len(students_placed),
            'avg_package': round(sum(packages) / len(packages), 2) if packages else 0,
            'companies': companies_list,
            'status_counts': status_counts
        }
    
    return render_template('pr_dashboard.html', pr_details=pr_details)

@app.route('/companies')
@login_required
def companies():
    placements = load_placements()
    
    # First, filter placements by campus type BEFORE getting unique companies
    # This ensures on-campus visualizations only include on-campus companies
    # Strictly filter: only "On Campus" (case-insensitive, any spacing) for on-campus
    # Everything else (Off Campus, Offcampus, empty, etc.) goes to off-campus
    campus_type_series = placements['campus_type'].astype(str).str.strip().str.casefold()
    
    # On-campus: must be exactly "on campus" (handles "On Campus", "ON CAMPUS", "on campus", etc.)
    on_campus_mask = campus_type_series == 'on campus'
    on_campus_placements = placements[on_campus_mask].copy()
    
    # Off-campus: everything that is NOT "on campus" (includes "Off Campus", "Offcampus", empty, etc.)
    off_campus_mask = ~on_campus_mask & (campus_type_series != '')
    off_campus_placements = placements[off_campus_mask].copy()
    
    # Verify filtering: ensure no off-campus records in on-campus data
    if not on_campus_placements.empty:
        # Double-check: remove any records that might have slipped through
        on_campus_placements = on_campus_placements[
            on_campus_placements['campus_type'].astype(str).str.strip().str.casefold() == 'on campus'
        ].copy()
    
    # Build unique company-level view for ALL companies (for the main table)
    unique_company_df = get_unique_company_records(placements)
    if not unique_company_df.empty:
        unique_company_df['campus_type'] = unique_company_df['campus_type'].fillna('').str.strip()
        unique_company_df['placement_origin'] = unique_company_df['placement_origin'].fillna('').str.strip()
        unique_company_df['status'] = unique_company_df['status'].fillna('').str.strip()
    
    # Calculate total students placed per company - count all students from student_names regardless of status
    company_student_counts = {}
    for _, row in placements.iterrows():
        company_id = str(row.get('company_id', '')).strip()
        if company_id and company_id != '':
            student_names = row.get('student_names')
            if pd.notna(student_names) and str(student_names).strip():
                # Count unique students (split by comma and count)
                names = [n.strip() for n in str(student_names).split(',') if n.strip()]
                if company_id not in company_student_counts:
                    company_student_counts[company_id] = set()
                company_student_counts[company_id].update([n.upper() for n in names])
    
    # Convert sets to counts and add to company overview
    company_overview = unique_company_df.to_dict('records')
    for company in company_overview:
        company_id = str(company.get('company_id', '')).strip()
        # Count unique students placed for this company
        unique_students = company_student_counts.get(company_id, set())
        company['total_students_placed'] = len(unique_students)
    
    # Build unique company-level view for ON-CAMPUS ONLY (for on-campus visualizations)
    on_campus_unique_df = get_unique_company_records(on_campus_placements)
    if not on_campus_unique_df.empty:
        on_campus_unique_df['campus_type'] = on_campus_unique_df['campus_type'].fillna('').str.strip()
        on_campus_unique_df['placement_origin'] = on_campus_unique_df['placement_origin'].fillna('').str.strip()
        on_campus_unique_df['status'] = on_campus_unique_df['status'].fillna('').str.strip()
        
        # CRITICAL: Double-check and remove any off-campus companies that might have slipped through
        # Filter out any companies where campus_type is NOT "On Campus"
        on_campus_unique_df = on_campus_unique_df[
            on_campus_unique_df['campus_type'].str.casefold() == 'on campus'
        ].copy()
    
    # Build unique company-level view for OFF-CAMPUS ONLY (for off-campus visualizations)
    off_campus_unique_df = get_unique_company_records(off_campus_placements)
    if not off_campus_unique_df.empty:
        off_campus_unique_df['campus_type'] = off_campus_unique_df['campus_type'].fillna('').str.strip()
        off_campus_unique_df['placement_origin'] = off_campus_unique_df['placement_origin'].fillna('').str.strip()
        off_campus_unique_df['status'] = off_campus_unique_df['status'].fillna('').str.strip()
        
        # CRITICAL: Double-check and remove any on-campus companies
        # Filter out any companies where campus_type IS "On Campus"
        off_campus_unique_df = off_campus_unique_df[
            off_campus_unique_df['campus_type'].str.casefold() != 'on campus'
        ].copy()
    
    # Use the filtered dataframes for visualizations
    on_campus_df = on_campus_unique_df if not on_campus_unique_df.empty else pd.DataFrame()
    off_campus_df = off_campus_unique_df if not off_campus_unique_df.empty else pd.DataFrame()
    
    # Calculate status statistics based on unique companies
    def _status_counts(df):
        stats = {}
        if df.empty:
            return stats
        for _, row in df.iterrows():
            status_str = str(row.get('status', '')).strip() or 'Unknown'
            stats[status_str] = stats.get(status_str, 0) + 1
        return stats
    
    on_campus_status_stats = _status_counts(on_campus_df)
    off_campus_status_stats = _status_counts(off_campus_df)
    
    # On-campus detailed breakdown: Status -> Origin
    on_campus_status_origin = {}
    if not on_campus_df.empty:
        for _, row in on_campus_df.iterrows():
            status = str(row.get('status', '')).strip() or 'Unknown'
            origin = str(row.get('placement_origin', '')).strip() or 'Unknown'
            if status not in on_campus_status_origin:
                on_campus_status_origin[status] = {}
            on_campus_status_origin[status][origin] = on_campus_status_origin[status].get(origin, 0) + 1
    
    # Completed on-campus breakdown (CPCG vs Department)
    completed_on_campus_breakdown = {}
    if not on_campus_df.empty:
        completed_df = on_campus_df[on_campus_df['status'].str.lower() == 'completed']
        for _, row in completed_df.iterrows():
            origin = str(row.get('placement_origin', '')).strip() or 'Unknown'
            completed_on_campus_breakdown[origin] = completed_on_campus_breakdown.get(origin, 0) + 1
    
    # Off-campus origin snapshot
    off_campus_origin_stats = {}
    if not off_campus_df.empty:
        for _, row in off_campus_df.iterrows():
            origin = str(row.get('placement_origin', '')).strip() or 'Unknown'
            off_campus_origin_stats[origin] = off_campus_origin_stats.get(origin, 0) + 1
    
    # Build company-wise records for easy understanding
    # Group all records by company_id to show all records per company
    company_wise_records = {}
    for _, row in placements.iterrows():
        company_id = str(row.get('company_id', '')).strip()
        if company_id and company_id != '':
            if company_id not in company_wise_records:
                company_wise_records[company_id] = {
                    'company_id': company_id,
                    'company_name': str(row.get('company_name', '')).strip(),
                    'campus_type': str(row.get('campus_type', '')).strip(),
                    'pr_assigned': str(row.get('pr_assigned', '')).strip(),
                    'pr_name': str(row.get('pr_name', '')).strip(),
                    'placement_origin': str(row.get('placement_origin', '')).strip(),
                    'records': []
                }
            
            # Add this record
            record_id = row.get('record_id')
            if pd.notna(record_id):
                try:
                    record_id = int(float(record_id))
                except (ValueError, TypeError):
                    record_id = None
            
            company_wise_records[company_id]['records'].append({
                'record_id': record_id,
                'status': str(row.get('status', '')).strip(),
                'role': str(row.get('role', '')).strip(),
                'package': str(row.get('package', '')).strip(),
                'student_names': str(row.get('student_names', '')).strip(),
                'noof_students_placed': str(row.get('noof_students_placed', '')).strip(),
                'class_distribution': str(row.get('class_distribution', '')).strip()
            })
    
    # Add student counts to company_wise_records
    for company_id, company_data in company_wise_records.items():
        unique_students = company_student_counts.get(company_id, set())
        company_data['total_students_placed'] = len(unique_students)
    
    # Convert to list and sort by company_id
    company_wise_list = sorted(company_wise_records.values(), key=lambda x: x['company_id'])
    
    # Replace NaN with empty strings for display
    placements = placements.fillna('')
    companies_list = placements.to_dict('records')
    # Convert dataframes to dict for template (for modal filtering)
    on_campus_companies_list = on_campus_df.to_dict('records') if not on_campus_df.empty else []
    off_campus_companies_list = off_campus_df.to_dict('records') if not off_campus_df.empty else []
    
    return render_template('companies.html',
                           companies=companies_list,
                           company_overview=company_overview,
                           company_wise_records=company_wise_list,
                           company_count=len(company_overview),
                           pr_mapping=PR_MAPPING,
                           on_campus_status_stats=on_campus_status_stats,
                           on_campus_status_origin=on_campus_status_origin,
                           completed_on_campus_breakdown=completed_on_campus_breakdown,
                           off_campus_status_stats=off_campus_status_stats,
                           off_campus_origin_stats=off_campus_origin_stats,
                           on_campus_total=len(on_campus_df),
                           off_campus_total=len(off_campus_df),
                           on_campus_companies=on_campus_companies_list,
                           off_campus_companies=off_campus_companies_list)

@app.route('/ongoing_companies')
@admin_required
def ongoing_companies():
    """
    Display all companies with ongoing status for easy management.
    Companies are identified by company_id. If ANY record for a company is "Completed",
    the company is considered completed and excluded from this list.
    """
    placements = load_placements()
    
    # First, identify companies that have ANY completed records (exclude these)
    completed_company_ids = set()
    for _, row in placements.iterrows():
        company_id = str(row.get('company_id', '')).strip()
        status = str(row.get('status', '')).strip().lower()
        if company_id and status == 'completed':
            completed_company_ids.add(company_id)
    
    # Filter ongoing companies, but exclude companies that have any completed records
    ongoing_mask = placements['status'].astype(str).str.strip().str.lower().isin(['on-going', 'ongoing', 'on going'])
    ongoing_placements = placements[ongoing_mask].copy()
    
    # Remove companies that have any completed records
    if not ongoing_placements.empty:
        ongoing_placements = ongoing_placements[
            ~ongoing_placements['company_id'].astype(str).str.strip().isin(completed_company_ids)
        ].copy()
    
    # Get unique company records
    unique_companies = {}
    for idx, row in ongoing_placements.iterrows():
        # Helper function to safely get values from pandas Series
        def safe_get(key, default=''):
            if key not in row.index:
                return default
            value = row[key]
            # Convert NaN to default
            if pd.isna(value):
                return default
            # Convert to string for text fields
            if isinstance(default, str):
                return str(value) if value is not None else default
            # Return as-is for numeric fields
            return value
        
        company_id = str(safe_get('company_id', '')).strip()
        if company_id and company_id != 'nan':
            if company_id not in unique_companies:
                unique_companies[company_id] = {
                    'company_id': company_id,
                    'company_name': safe_get('company_name', ''),
                    'campus_type': safe_get('campus_type', ''),
                    'pr_assigned': safe_get('pr_assigned', ''),
                    'pr_name': safe_get('pr_name', ''),
                    'placement_origin': safe_get('placement_origin', ''),
                    'status': safe_get('status', ''),
                    'records': []
                }
            
            # Get record_id as int if possible
            record_id_val = safe_get('record_id', None)
            if record_id_val is not None and not pd.isna(record_id_val):
                try:
                    record_id_val = int(float(record_id_val))
                except (ValueError, TypeError):
                    record_id_val = None
            else:
                record_id_val = None
            
            unique_companies[company_id]['records'].append({
                'record_id': record_id_val,
                'role': safe_get('role', ''),
                'package': safe_get('package', ''),
                'student_names': safe_get('student_names', ''),
                'noof_students_placed': safe_get('noof_students_placed', '')
            })
    
    # Convert to list for template
    companies_list = list(unique_companies.values())
    
    return render_template('ongoing_companies.html',
                         companies=companies_list,
                         pr_mapping=PR_MAPPING)

@app.route('/add_record', methods=['GET', 'POST'])
@admin_required
def add_record():
    # Get pre-fill values from query parameters (for ongoing companies)
    prefill = {
        'company_id': request.args.get('company_id', ''),
        'company_name': request.args.get('company_name', ''),
        'status': request.args.get('status', 'On-going')
    }
    
    if request.method == 'POST':
        placements = load_placements()
        
        # Generate unique record_id
        max_record_id = placements['record_id'].max() if len(placements) > 0 else 0
        new_record_id = max_record_id + 1
        
        # Get company name and check if it exists
        company_name = request.form.get('company_name', '').strip()
        provided_company_id = request.form.get('company_id', '').strip()
        
        # If company_id is provided, use it (for ongoing companies)
        if provided_company_id:
            new_id = provided_company_id
        else:
            # Check if company name already exists (exact match, case-insensitive)
            existing_company = placements[placements['company_name'].str.strip().str.upper() == company_name.upper()]
            
            if not existing_company.empty:
                # Reuse existing company ID
                new_id = existing_company.iloc[0]['company_id']
            else:
                # Generate new company ID
                existing_ids = placements['company_id'].tolist()
                max_id = 0
                for cid in existing_ids:
                    if isinstance(cid, str) and cid.startswith('CMP'):
                        try:
                            num = int(cid[3:])
                            max_id = max(max_id, num)
                        except:
                            pass
                new_id = f'CMP{str(max_id + 1).zfill(2)}'
        
        # Auto-detect class
        student_names = request.form.get('student_names', '').strip()
        class_dist = ''
        if student_names:
            names = [n.strip() for n in student_names.split(',')]
            classes = [get_student_class(name) for name in names]
            class_dist = ', '.join([c for c in classes if c])
        
        # Check if adding a Completed record when On-going record exists for same company
        new_status = request.form.get('status', '').strip()
        if new_status.lower() == 'completed' and new_id:
            existing_ongoing = placements[
                (placements['company_id'].astype(str).str.strip() == new_id) &
                (placements['status'].astype(str).str.strip().str.lower().isin(['on-going', 'ongoing', 'on going']))
            ]
            if not existing_ongoing.empty:
                ongoing_ids = existing_ongoing['record_id'].astype(str).tolist()
                flash(f'Note: This company already has On-going record(s) (ID: {", ".join(ongoing_ids)}). If you meant to update the status, please edit the existing record instead of creating a new one.', 'info')
        
        new_record = {
            'record_id': new_record_id,
            'company_id': new_id,
            'company_name': request.form.get('company_name'),
            'campus_type': request.form.get('campus_type'),
            'pr_assigned': request.form.get('pr_assigned'),
            'pr_name': PR_MAPPING.get(request.form.get('pr_assigned', ''), ''),
            'placement_origin': request.form.get('placement_origin'),
            'status': new_status,
            'noof_students_placed': request.form.get('noof_students_placed'),
            'role': request.form.get('role'),
            'package': request.form.get('package'),
            'student_names': student_names,
            'class_distribution': class_dist
        }
        
        placements = pd.concat([placements, pd.DataFrame([new_record])], ignore_index=True)
        save_placements(placements)
        flash('Record added successfully!', 'success')
        # Redirect to ongoing companies if it was an ongoing company
        if request.form.get('status', '').lower() in ['on-going', 'ongoing', 'on going']:
            return redirect(url_for('ongoing_companies'))
        return redirect(url_for('companies'))
    
    # Get pre-fill values from query parameters (for ongoing companies)
    prefill = {
        'company_id': request.args.get('company_id', ''),
        'company_name': request.args.get('company_name', ''),
        'status': request.args.get('status', '')
    }
    
    # Get all ongoing companies for dropdown
    placements = load_placements()
    
    # First, identify companies that have ANY completed records (exclude these)
    completed_company_ids = set()
    for _, row in placements.iterrows():
        company_id = str(row.get('company_id', '')).strip()
        status = str(row.get('status', '')).strip().lower()
        if company_id and status == 'completed':
            completed_company_ids.add(company_id)
    
    # Filter ongoing companies, but exclude companies that have any completed records
    ongoing_mask = placements['status'].astype(str).str.strip().str.lower().isin(['on-going', 'ongoing', 'on going'])
    ongoing_placements = placements[ongoing_mask].copy()
    
    # Remove companies that have any completed records
    if not ongoing_placements.empty:
        ongoing_placements = ongoing_placements[
            ~ongoing_placements['company_id'].astype(str).str.strip().isin(completed_company_ids)
        ].copy()
    
    # Get unique ongoing companies
    ongoing_companies = []
    if not ongoing_placements.empty:
        unique_companies = {}
        for _, row in ongoing_placements.iterrows():
            company_id = str(row.get('company_id', '')).strip()
            company_name = str(row.get('company_name', '')).strip()
            if company_id and company_id != 'nan' and company_id not in unique_companies:
                unique_companies[company_id] = company_name
        
        ongoing_companies = []
        for cid, name in sorted(unique_companies.items()):
            # Get additional company details from the first record
            company_record = ongoing_placements[ongoing_placements['company_id'].astype(str).str.strip() == cid].iloc[0]
            ongoing_companies.append({
                'id': cid,
                'name': name,
                'campus_type': str(company_record.get('campus_type', '')).strip() if pd.notna(company_record.get('campus_type')) else '',
                'placement_origin': str(company_record.get('placement_origin', '')).strip() if pd.notna(company_record.get('placement_origin')) else '',
                'pr_assigned': str(company_record.get('pr_assigned', '')).strip() if pd.notna(company_record.get('pr_assigned')) else ''
            })
    
    return render_template('add_record.html', 
                         pr_mapping=PR_MAPPING, 
                         prefill=prefill,
                         ongoing_companies=ongoing_companies)

@app.route('/edit_record/<int:record_id>', methods=['GET', 'POST'])
@admin_required
def edit_record(record_id):
    placements = load_placements()
    
    if request.method == 'POST':
        idx = placements[placements['record_id'] == record_id].index[0]
        
        # Get current record details before update
        current_record = placements.iloc[idx]
        current_status = str(current_record.get('status', '')).strip().lower()
        current_company_id = str(current_record.get('company_id', '')).strip()
        
        student_names = request.form.get('student_names', '').strip()
        class_dist = ''
        if student_names:
            names = [n.strip() for n in student_names.split(',')]
            classes = [get_student_class(name) for name in names]
            class_dist = ', '.join([c for c in classes if c])
        
        # Get the new status value
        new_status = request.form.get('status', '').strip()
        
        # Check for potential duplicate: if changing from On-going to Completed,
        # check if there's already a Completed record for the same company
        if (current_status in ['on-going', 'ongoing', 'on going'] and 
            new_status.lower() == 'completed' and 
            current_company_id):
            
            # Check for existing Completed records with same company_id (excluding current record)
            existing_completed = placements[
                (placements['record_id'] != record_id) &
                (placements['company_id'].astype(str).str.strip() == current_company_id) &
                (placements['status'].astype(str).str.strip().str.lower() == 'completed')
            ]
            
            if not existing_completed.empty:
                # Warn about existing completed record but still allow the update
                flash(f'Warning: There is already a Completed record for this company (record_id: {", ".join(existing_completed["record_id"].astype(str).tolist())}). Make sure you are updating the correct record, not creating a duplicate.', 'warning')
        
        placements.at[idx, 'company_name'] = request.form.get('company_name')
        placements.at[idx, 'campus_type'] = request.form.get('campus_type')
        placements.at[idx, 'pr_assigned'] = request.form.get('pr_assigned')
        placements.at[idx, 'pr_name'] = PR_MAPPING.get(request.form.get('pr_assigned', ''), '')
        placements.at[idx, 'placement_origin'] = request.form.get('placement_origin')
        placements.at[idx, 'status'] = new_status
        placements.at[idx, 'noof_students_placed'] = request.form.get('noof_students_placed')
        placements.at[idx, 'role'] = request.form.get('role')
        placements.at[idx, 'package'] = request.form.get('package')
        placements.at[idx, 'student_names'] = student_names
        placements.at[idx, 'class_distribution'] = class_dist
        
        # Save to CSV - this ensures the change is persisted
        save_placements(placements)
        
        # Show appropriate message based on status change
        if new_status.lower() == 'completed':
            flash('Record updated successfully! Status changed to Completed. Students will now be counted in placement statistics.', 'success')
        else:
            flash('Record updated successfully!', 'success')
        
        # Redirect based on status - if completed, go to dashboard to see updated count
        if new_status.lower() == 'completed':
            return redirect(url_for('dashboard'))
        return redirect(url_for('companies'))
    
    # Replace NaN with empty strings for display
    record = placements[placements['record_id'] == record_id].iloc[0].fillna('').to_dict()
    return render_template('edit_record.html', record=record, pr_mapping=PR_MAPPING)

@app.route('/delete_record/<int:record_id>')
@admin_required
def delete_record(record_id):
    placements = load_placements()
    placements = placements[placements['record_id'] != record_id]
    save_placements(placements)
    flash('Record deleted successfully!', 'success')
    return redirect(url_for('companies'))

@app.route('/api/student_class/<name>')
@login_required
def api_student_class(name):
    student_class = get_student_class(name)
    return jsonify({'class': student_class})

@app.route('/api/search_students')
@login_required
def search_students():
    query = request.args.get('q', '').strip().upper()
    if len(query) < 2:
        return jsonify([])
    
    students = load_students()
    placements = load_placements()
    
    # Get list of already placed students - count all students from student_names regardless of status
    placed_students = set()
    for _, row in placements.iterrows():
        if pd.notna(row.get('student_names')) and str(row['student_names']).strip():
            names = [n.strip().upper() for n in str(row['student_names']).split(',') if n.strip()]
            placed_students.update(names)
    
    # Search by name
    name_matches = students[students['Name'].str.upper().str.contains(query, na=False)]
    # Search by register number
    reg_no_matches = students[students['Reg.no'].astype(str).str.upper().str.contains(query, na=False)]
    
    # Combine and remove duplicates
    all_matches = pd.concat([name_matches, reg_no_matches]).drop_duplicates()
    
    results = []
    for _, student in all_matches.head(10).iterrows():  # Limit to 10 results
        is_placed = student['Name'].upper() in placed_students
        results.append({
            'name': str(student['Name']),
            'reg_no': str(student['Reg.no']),
            'class': str(student['Class']) if pd.notna(student['Class']) else '',
            'is_placed': bool(is_placed)
        })
    
    return jsonify(results)

@app.route('/api/company_stats/<company_id>')
@login_required
def company_stats(company_id):
    try:
        placements = load_placements()
        students_df = load_students()
        
        # Get all records for this company (handle both string and numeric IDs)
        company_records = placements[placements['company_id'].astype(str) == str(company_id)]
        
        if company_records.empty:
            return jsonify({'error': 'Company not found'}), 404
        
        company_name = company_records.iloc[0]['company_name']
        
        # Collect all students and their details
        student_details = []
        class_count = {}
        
        for _, record in company_records.iterrows():
            if pd.notna(record.get('student_names')) and str(record.get('student_names', '')).strip():
                names = [n.strip() for n in str(record['student_names']).split(',') if n.strip()]
                for name in names:
                    # Use improved function to get student details
                    student_info = get_student_details(name)
                    
                    if student_info:
                        # Student found in database
                        student_details.append({
                            'name': student_info['name'],
                            'reg_no': str(student_info['reg_no']),
                            'class': student_info['class'],
                            'role': str(record['role']) if pd.notna(record.get('role')) else 'N/A',
                            'package': str(record['package']) if pd.notna(record.get('package')) else 'N/A'
                        })
                        
                        if student_info['class']:
                            class_count[student_info['class']] = class_count.get(student_info['class'], 0) + 1
                    else:
                        # Student not found - use name as entered
                        print(f"Warning: Student '{name}' not found in database")
                        student_details.append({
                            'name': name,
                            'reg_no': 'N/A',
                            'class': 'Unknown',
                            'role': str(record['role']) if pd.notna(record.get('role')) else 'N/A',
                            'package': str(record['package']) if pd.notna(record.get('package')) else 'N/A'
                        })
        
        return jsonify({
            'company_id': str(company_id),
            'company_name': str(company_name),
            'total_students': len(student_details),
            'students': student_details,
            'class_distribution': class_count,
            'total_drives': len(company_records)
        })
    except Exception as e:
        print(f"Error in company_stats: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error loading statistics: {str(e)}'}), 500


# Helper function to convert pandas/numpy types to native Python types for JSON serialization
def convert_to_native(obj):
    """Convert pandas/numpy types to native Python types."""
    import numpy as np
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj) if not np.isnan(obj) else None
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_to_native(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_native(item) for item in obj]
    elif pd.isna(obj):
        return None
    return obj

# Get complete student application history from all ANALYSIS CSVs
def get_student_application_history(student_name):
    """
    Get complete application history for a specific student across all companies.
    Returns detailed progression through each company's recruitment rounds.
    """
    students_df = load_students()
    placements = load_placements()
    
    # Get company name mapping from placements
    company_name_map = {}
    if not placements.empty and 'company_id' in placements.columns:
        for _, row in placements.iterrows():
            company_id = str(row.get('company_id', '')).strip()
            company_name = str(row.get('company_name', '')).strip()
            if company_id and company_name:
                company_name_map[company_id] = company_name
    
    # Find student in FULL NAME LIST
    student_info = get_student_details(student_name)
    if not student_info:
        return None
    
    student_name_upper = student_info['name'].upper()
    
    # Load all ANALYSIS CSVs and track student's progress
    application_history = []
    companies_not_applied = []
    
    if not os.path.exists(ANALYSIS_FOLDER):
        return None
    
    # Get list of all company IDs from ANALYSIS folder
    all_company_ids = set()
    for filename in os.listdir(ANALYSIS_FOLDER):
        if filename.endswith('.csv'):
            company_id = filename.replace('.csv', '').strip()
            all_company_ids.add(company_id)
    
    # Process each company's analysis CSV
    for filename in os.listdir(ANALYSIS_FOLDER):
        if filename.endswith('.csv'):
            company_id = filename.replace('.csv', '').strip()
            filepath = os.path.join(ANALYSIS_FOLDER, filename)
            company_name = company_name_map.get(company_id, company_id)
            
            try:
                df = pd.read_csv(filepath)
                df.columns = df.columns.str.strip()
                
                # Find name column and register number column
                name_col = None
                reg_no_col = None
                for col in df.columns:
                    if 'name' in col.lower() and 'student' in col.lower():
                        name_col = col
                    if 'register' in col.lower() and 'number' in col.lower():
                        reg_no_col = col
                
                if name_col is None:
                    continue
                
                # Get student info for matching
                student_info = get_student_details(student_name)
                student_reg_no = student_info['reg_no'] if student_info else None
                student_reg_no_upper = str(student_reg_no).strip().upper() if student_reg_no else None
                
                # Find student in this company's data by name or register number
                student_row = None
                for _, row in df.iterrows():
                    row_name = str(row[name_col]).strip().upper()
                    
                    # Try exact name match
                    if row_name == student_name_upper:
                        student_row = row
                        break
                    
                    # Try register number match if available
                    if reg_no_col and reg_no_col in row.index and student_reg_no_upper:
                        row_reg_no = str(row[reg_no_col]).strip().upper()
                        if row_reg_no == student_reg_no_upper:
                            student_row = row
                            break
                    
                    # Try fuzzy name match
                    if student_name_upper in row_name or row_name in student_name_upper:
                        student_row = row
                        break
                
                if student_row is None:
                    companies_not_applied.append({
                        'company_id': str(company_id),
                        'company_name': str(company_name)
                    })
                    continue
                
                # Get stages (exclude Name and Register Number columns - these are identifiers, not rounds)
                exclude_cols = [name_col]
                if reg_no_col:
                    exclude_cols.append(reg_no_col)
                # Also exclude common variations
                exclude_cols.extend(['Register Number', 'Name', 'Name of the Student', 'Reg.no', 'Reg No'])
                stages = [col for col in df.columns if col not in exclude_cols]
                
                # Track progression through stages
                progression = []
                applied = False
                last_passed_stage = None
                reached_stage_index = -1
                failed_at_stage = None
                
                for idx, stage in enumerate(stages):
                    if stage in student_row.index:
                        value = student_row[stage]
                        # Convert to int if possible, handle NaN
                        if pd.isna(value):
                            passed = False
                        elif isinstance(value, (int, float)):
                            passed = int(value) == 1
                        else:
                            passed = str(value).strip() == '1'
                        
                        # Track if student applied (first stage or any stage with "Applied" in name)
                        if idx == 0:
                            applied = passed  # First stage always indicates application
                        elif 'Applied' in stage and passed:
                            applied = True
                        
                        if passed:
                            last_passed_stage = stage
                            reached_stage_index = idx
                            progression.append({
                                'stage': stage,
                                'passed': True,
                                'index': idx
                            })
                        else:
                            progression.append({
                                'stage': stage,
                                'passed': False,
                                'index': idx
                            })
                            
                            # If this is the first stage after last passed, this is where they failed
                            if last_passed_stage and failed_at_stage is None and idx > reached_stage_index:
                                failed_at_stage = stage
                
                # Only add if student actually applied
                if not applied:
                    companies_not_applied.append({
                        'company_id': str(company_id),
                        'company_name': str(company_name)
                    })
                    continue
                
                # Determine final status
                if last_passed_stage == 'Selected' or (stages and last_passed_stage == stages[-1] and reached_stage_index == len(stages) - 1):
                    final_status = 'Selected'
                elif failed_at_stage:
                    final_status = f'Failed at {failed_at_stage}'
                elif last_passed_stage and last_passed_stage != stages[0]:
                    final_status = f'Reached {last_passed_stage}'
                else:
                    final_status = 'Applied Only'
                
                # Count stages passed
                stages_passed = sum(1 for p in progression if p.get('passed', False))
                
                application_history.append({
                    'company_id': str(company_id),
                    'company_name': str(company_name),
                    'stages': [str(s) for s in stages],
                    'progression': progression,
                    'stages_passed': int(stages_passed),
                    'total_stages': int(len(stages)),
                    'last_passed_stage': str(last_passed_stage) if last_passed_stage else None,
                    'failed_at_stage': str(failed_at_stage) if failed_at_stage else None,
                    'final_status': str(final_status),
                    'reached_final': bool(reached_stage_index == len(stages) - 1 if stages else False)
                })
                
            except Exception as e:
                print(f"Error processing {filename}: {e}")
                continue
    
    # Calculate statistics (convert to native Python types)
    total_applications = int(len(application_history))
    total_selected = int(sum(1 for app in application_history if app['final_status'] == 'Selected'))
    total_reached_final = int(sum(1 for app in application_history if app['reached_final']))
    failed_at_final = int(sum(1 for app in application_history 
                         if app['reached_final'] and app['final_status'] != 'Selected'))
    
    # Count failure patterns
    failure_patterns = {}
    for app in application_history:
        if app['failed_at_stage']:
            stage = str(app['failed_at_stage'])
            failure_patterns[stage] = int(failure_patterns.get(stage, 0) + 1)
    
    # Calculate average stages reached
    avg_stages_reached = float(round(sum(app['stages_passed'] for app in application_history) / total_applications, 2)) if total_applications > 0 else 0.0
    
    # Convert student_info to native types
    student_info_native = {
        'name': str(student_info['name']),
        'reg_no': str(student_info['reg_no']),
        'class': str(student_info['class']) if student_info['class'] else None
    }
    
    return {
        'student_info': student_info_native,
        'application_history': application_history,
        'companies_not_applied': companies_not_applied,
        'statistics': {
            'total_applications': total_applications,
            'total_selected': total_selected,
            'total_reached_final': total_reached_final,
            'failed_at_final': failed_at_final,
            'total_companies_available': int(len(all_company_ids)),
            'companies_not_applied_count': int(len(companies_not_applied)),
            'avg_stages_reached': avg_stages_reached,
            'selection_rate': float(round((total_selected / total_applications * 100), 2)) if total_applications > 0 else 0.0,
            'final_round_failure_rate': float(round((failed_at_final / total_reached_final * 100), 2)) if total_reached_final > 0 else 0.0
        },
        'failure_patterns': {str(k): int(v) for k, v in failure_patterns.items()}
    }

# Load all company analysis data from ANALYSIS folder
def load_all_company_analysis():
    """
    Load all company analysis CSVs from the ANALYSIS folder.
    Returns a dictionary mapping company_id to analysis data.
    """
    analysis_data = {}
    
    if not os.path.exists(ANALYSIS_FOLDER):
        return analysis_data
    
    # Get company name mapping from placements
    placements = load_placements()
    company_name_map = {}
    if not placements.empty and 'company_id' in placements.columns:
        for _, row in placements.iterrows():
            company_id = str(row.get('company_id', '')).strip()
            company_name = str(row.get('company_name', '')).strip()
            if company_id and company_name:
                company_name_map[company_id] = company_name
    
    # Load all CSV files in ANALYSIS folder
    for filename in os.listdir(ANALYSIS_FOLDER):
        if filename.endswith('.csv'):
            company_id = filename.replace('.csv', '').strip()
            filepath = os.path.join(ANALYSIS_FOLDER, filename)
            
            try:
                df = pd.read_csv(filepath)
                df.columns = df.columns.str.strip()
                
                # Get company name
                company_name = company_name_map.get(company_id, company_id)
                
                # Identify stage columns (exclude Name and Register Number - these are identifiers, not rounds)
                exclude_cols = ['Name of the Student', 'Register Number', 'Name', 'Reg.no', 'Reg No']
                stage_columns = [col for col in df.columns if col not in exclude_cols]
                
                analysis_data[company_id] = {
                    'company_id': company_id,
                    'company_name': company_name,
                    'data': df,
                    'stages': stage_columns,
                    'filepath': filepath
                }
            except Exception as e:
                print(f"Error loading {filename}: {e}")
                continue
    
    return analysis_data

# Get company-wise funnel analysis
def get_company_funnel_analysis():
    """
    Analyze funnel progression for each company.
    Shows how many students applied and how many passed each round.
    """
    all_analysis = load_all_company_analysis()
    funnels = {}
    
    for company_id, company_data in all_analysis.items():
        df = company_data['data']
        stages = company_data['stages']
        
        # Count students at each stage
        stage_counts = {}
        for stage in stages:
            if stage in df.columns:
                # Count how many students passed this stage (value = 1)
                count = df[stage].sum() if stage in df.columns else 0
                # Get scalar value
                if isinstance(count, (int, float)):
                    stage_counts[stage] = int(count)
                elif hasattr(count, 'item'):
                    stage_counts[stage] = int(count.item())
                else:
                    stage_counts[stage] = 0
        
        # Calculate conversion rates between stages
        conversions = {}
        stage_list = [s for s in stages if s in df.columns]
        for i in range(len(stage_list) - 1):
            current_stage = stage_list[i]
            next_stage = stage_list[i + 1]
            current_count = stage_counts.get(current_stage, 0)
            next_count = stage_counts.get(next_stage, 0)
            
            if current_count > 0:
                conversion_rate = round((next_count / current_count) * 100, 2)
            else:
                conversion_rate = 0
            
            conversions[f"{current_stage} → {next_stage}"] = {
                'from': current_count,
                'to': next_count,
                'rate': conversion_rate
            }
        
        funnels[company_id] = {
            'company_id': company_id,
            'company_name': company_data['company_name'],
            'stages': stage_list,
            'stage_counts': stage_counts,
            'conversions': conversions,
            'total_applied': stage_counts.get(stage_list[0] if stage_list else 'Applied', 0),
            'total_selected': stage_counts.get('Selected', stage_counts.get(stage_list[-1] if stage_list else 'Selected', 0))
        }
    
    return funnels

# Get comprehensive placement statistics combining ANALYSIS folder and Master_Placement_Fila.csv
def get_comprehensive_placement_statistics():
    """
    Combine data from ANALYSIS folder (round-wise progression) and Master_Placement_Fila.csv (placed students)
    to create comprehensive placement statistics.
    
    Logic:
    - One student can apply to multiple companies
    - Once placed, student is "blocked" (excluded from active application counts)
    - Count unique students, not total applications
    - Track students who apply most vs least
    """
    students_df = load_students()
    placements = load_placements()
    all_analysis = load_all_company_analysis()
    
    # Get all placed students from Master_Placement_Fila.csv (these are "blocked")
    # Count all students from student_names regardless of status
    placed_students = set()
    placed_students_details = {}
    for _, row in placements.iterrows():
        if pd.notna(row.get('student_names')) and str(row['student_names']).strip():
            names = [n.strip().upper() for n in str(row['student_names']).split(',') if n.strip()]
            for name in names:
                placed_students.add(name)
                if name not in placed_students_details:
                    placed_students_details[name] = {
                        'company_id': str(row.get('company_id', '')),
                        'company_name': str(row.get('company_name', '')),
                        'role': str(row.get('role', '')),
                        'package': str(row.get('package', '')),
                        'status': str(row.get('status', ''))
                    }
    
    # Build student lookup from FULL NAME LIST
    student_lookup = {}
    for _, row in students_df.iterrows():
        name_upper = str(row['Name']).strip().upper()
        student_lookup[name_upper] = {
            'name': row['Name'],
            'reg_no': str(row['Reg.no']),
            'class': str(row['Class']) if pd.notna(row['Class']) else 'Unknown'
        }
    
    # Track unique students (not applications)
    students_applied = set()  # Unique students who applied (at least once)
    students_application_count = {}  # student -> number of companies applied
    students_active_applications = {}  # student -> list of companies they applied to (only if not placed)
    students_never_applied = set()  # Students who never applied
    students_round_participation = {}  # student -> {stage: count} - how many times they passed each round
    
    # Initialize all students as never applied
    for _, row in students_df.iterrows():
        name_upper = str(row['Name']).strip().upper()
        students_never_applied.add(name_upper)
    
    # Aggregate statistics from all companies
    overall_funnel = {}  # Stage -> {unique_students_applied: set, unique_students_passed: set}
    company_stats = {}  # company_id -> stats
    round_pass_rates = {}  # Round name -> {passed: set of students, total: set of students}
    class_stats = {
        'MCA A': {'unique_applied': set(), 'placed': set(), 'total_applications': 0},
        'MCA B': {'unique_applied': set(), 'placed': set(), 'total_applications': 0},
        'MSc AIML': {'unique_applied': set(), 'placed': set(), 'total_applications': 0}
    }
    
    # Process each company's analysis
    for company_id, company_data in all_analysis.items():
        df = company_data['data']
        company_name = company_data['company_name']
        stages = company_data['stages']
        
        if not stages:
            continue
        
        # Find name column
        name_col = None
        for col in df.columns:
            if 'name' in col.lower() and 'student' in col.lower():
                name_col = col
                break
        
        if name_col is None:
            continue
        
        # Initialize company stats
        if company_id not in company_stats:
            company_stats[company_id] = {
                'company_id': company_id,
                'company_name': company_name,
                'stages': stages,
                'funnel': {},
                'total_applied': 0,
                'total_placed': 0,
                'placed_students': []
            }
        
        # Process each student in this company
        for _, row in df.iterrows():
            student_name = str(row[name_col]).strip().upper()
            if not student_name or student_name == 'NAN':
                continue
            
            # Get student class
            student_class = 'Unknown'
            if student_name in student_lookup:
                student_class = student_lookup[student_name]['class']
            
            # Check if student applied (first stage = 1)
            first_stage = stages[0] if stages else None
            if first_stage and first_stage in row.index:
                value = row[first_stage]
                if pd.isna(value):
                    applied = False
                elif isinstance(value, (int, float)):
                    applied = int(value) == 1
                else:
                    applied = str(value).strip() == '1'
            else:
                applied = False
            
            if not applied:
                continue
            
            # Check if student is already placed (blocked)
            is_placed = student_name in placed_students
            
            # Track unique student applied (only count once per student, not per application)
            students_applied.add(student_name)
            students_never_applied.discard(student_name)  # Remove from never applied
            
            # Track application count per student
            if student_name not in students_application_count:
                students_application_count[student_name] = 0
            students_application_count[student_name] += 1
            
            # Track active applications (only if not placed)
            if not is_placed:
                if student_name not in students_active_applications:
                    students_active_applications[student_name] = []
                students_active_applications[student_name].append(company_id)
            
            # Update class stats - track unique students
            if student_class in class_stats:
                class_stats[student_class]['unique_applied'].add(student_name)
                class_stats[student_class]['total_applications'] += 1
                if is_placed:
                    class_stats[student_class]['placed'].add(student_name)
            
            # Track progression through stages (count unique students, not applications)
            # Proper funnel logic: each stage only counts students who passed all previous stages
            student_key = f"{student_name}_{company_id}"  # Unique per company application
            
            # Initialize all stages first
            for stage in stages:
                if stage not in overall_funnel:
                    overall_funnel[stage] = {'reached': set(), 'passed': set()}
                if stage not in company_stats[company_id]['funnel']:
                    company_stats[company_id]['funnel'][stage] = {'reached': set(), 'passed': set()}
            
            # Track which stages student passed
            student_passed_stages = []
            
            for idx, stage in enumerate(stages):
                # First stage: Applied - all students who applied reach this stage
                if idx == 0:
                    overall_funnel[stage]['reached'].add(student_key)
                    overall_funnel[stage]['passed'].add(student_key)  # Applied = passed first stage
                    company_stats[company_id]['funnel'][stage]['reached'].add(student_name)
                    company_stats[company_id]['funnel'][stage]['passed'].add(student_name)
                    company_stats[company_id]['total_applied'] = len(company_stats[company_id]['funnel'][stage]['reached'])
                    student_passed_stages.append(stage)
                    continue  # Move to next stage
                
                # For subsequent stages: only check if student passed previous stage
                previous_stage = stages[idx - 1]
                if previous_stage not in student_passed_stages:
                    # Student didn't pass previous stage, so they can't reach this stage
                    break
                
                # Student reached this stage (they passed all previous stages)
                overall_funnel[stage]['reached'].add(student_key)
                company_stats[company_id]['funnel'][stage]['reached'].add(student_name)
                
                # Check if passed this stage
                if stage in row.index:
                    value = row[stage]
                    if pd.isna(value):
                        passed = False
                    elif isinstance(value, (int, float)):
                        passed = int(value) == 1
                    else:
                        passed = str(value).strip() == '1'
                    
                    if passed:
                        overall_funnel[stage]['passed'].add(student_key)
                        company_stats[company_id]['funnel'][stage]['passed'].add(student_name)
                        student_passed_stages.append(stage)
                        
                        # Track student's round participation
                        if student_name not in students_round_participation:
                            students_round_participation[student_name] = {}
                        if stage not in students_round_participation[student_name]:
                            students_round_participation[student_name][stage] = 0
                        students_round_participation[student_name][stage] += 1
                    else:
                        # Student reached this stage but didn't pass - they stop here
                        break
            
            # Update round pass rates correctly:
            # Track which stages the student reached and passed
            student_key = f"{student_name}_{company_id}"
            
            for idx, stage in enumerate(stages):
                if stage not in round_pass_rates:
                    round_pass_rates[stage] = {'passed': set(), 'total': set()}
                
                # First stage: all who applied reached it
                if idx == 0:
                    round_pass_rates[stage]['total'].add(student_key)
                    if stage in overall_funnel and student_key in overall_funnel[stage].get('passed', set()):
                        round_pass_rates[stage]['passed'].add(student_key)
                else:
                    # Subsequent stages: only count if student reached this stage
                    if stage in overall_funnel and student_key in overall_funnel[stage].get('reached', set()):
                        round_pass_rates[stage]['total'].add(student_key)
                        if student_key in overall_funnel[stage].get('passed', set()):
                            round_pass_rates[stage]['passed'].add(student_key)
            
            # Check if student is placed in this company
            if student_name in placed_students:
                placed_info = placed_students_details.get(student_name, {})
                if str(placed_info.get('company_id', '')) == str(company_id):
                    # Count unique placed students
                    if student_name not in [s['name'].upper() for s in company_stats[company_id]['placed_students']]:
                        company_stats[company_id]['placed_students'].append({
                            'name': student_lookup.get(student_name, {}).get('name', student_name),
                            'reg_no': student_lookup.get(student_name, {}).get('reg_no', ''),
                            'role': placed_info.get('role', ''),
                            'package': placed_info.get('package', '')
                        })
                    company_stats[company_id]['total_placed'] = len(company_stats[company_id]['placed_students'])
    
    # Calculate overall statistics (unique students)
    total_students = len(students_df)
    total_applied = len(students_applied)  # Unique students who applied
    total_placed = len(placed_students)  # Unique students placed
    # total_never_applied will be calculated later after filtering out placed students
    total_active_applicants = len(students_active_applications)  # Students still applying (not placed)
    
    placement_rate = round((total_placed / total_students * 100), 2) if total_students > 0 else 0
    application_rate = round((total_applied / total_students * 100), 2) if total_students > 0 else 0
    selection_rate = round((total_placed / total_applied * 100), 2) if total_applied > 0 else 0
    
    # Calculate average applications per student (only for those who applied)
    avg_applications = round(sum(students_application_count.values()) / len(students_application_count), 2) if students_application_count else 0
    
    # Find most active and least active students (exclude placed students)
    # Filter out placed students from application count
    active_students_only = {name: count for name, count in students_application_count.items() 
                           if name not in placed_students}
    
    most_active_students = sorted(active_students_only.items(), key=lambda x: x[1], reverse=True)[:20]
    least_active_students = sorted(active_students_only.items(), key=lambda x: x[1])[:20]
    
    # Students who never applied (exclude placed students - they shouldn't be in this list anyway)
    never_applied_list = []
    for student_name in students_never_applied:
        # Exclude placed students from never applied list
        if student_name not in placed_students and student_name in student_lookup:
            never_applied_list.append({
                'name': student_lookup[student_name]['name'],
                'reg_no': student_lookup[student_name]['reg_no'],
                'class': student_lookup[student_name]['class']
            })
    
    # Update total_never_applied count to exclude placed students
    total_never_applied = len([s for s in students_never_applied if s not in placed_students])
    
    # Build funnel data for visualization - collect all unique stages from all companies
    all_stages_ordered = []
    for company_id, company_data in all_analysis.items():
        stages = company_data.get('stages', [])
        for stage in stages:
            if stage not in all_stages_ordered:
                all_stages_ordered.append(stage)
    
    # Build funnel data for visualization (proper funnel progression)
    # Funnel shows: how many students reached each stage (passed all previous stages)
    funnel_data = []
    if overall_funnel and all_stages_ordered:
        for stage in all_stages_ordered:
            if stage in overall_funnel:
                reached_count = len(overall_funnel[stage]['reached'])  # Students who reached this stage
                passed_count = len(overall_funnel[stage]['passed'])  # Students who passed this stage
                
                # For funnel display: show how many reached each stage
                # "Applied" shows total who applied
                # Subsequent stages show how many passed all previous stages
                funnel_data.append({
                    'stage': stage,
                    'reached': int(reached_count),  # Students who reached this stage
                    'passed': int(passed_count),  # Students who passed this stage
                    'pass_rate': round((passed_count / reached_count * 100), 2) if reached_count > 0 else 0
                })
    
    # Calculate round pass rates (unique students)
    round_pass_rate_data = []
    for stage, rates in round_pass_rates.items():
        passed_count = len(rates['passed'])
        total_count = len(rates['total'])
        round_pass_rate_data.append({
            'round': stage,
            'passed': int(passed_count),
            'total': int(total_count),
            'pass_rate': round((passed_count / total_count * 100), 2) if total_count > 0 else 0
        })
    
    # Convert company stats to list (count unique students)
    company_stats_list = []
    for company_id, stats in company_stats.items():
        # Count unique students from funnel
        unique_applied = 0
        if stats['funnel']:
            first_stage = stats['stages'][0] if stats['stages'] else None
            if first_stage and first_stage in stats['funnel']:
                unique_applied = len(stats['funnel'][first_stage].get('reached', set()))
        
        company_stats_list.append({
            'company_id': company_id,
            'company_name': stats['company_name'],
            'total_applied': int(unique_applied),
            'total_placed': int(stats['total_placed']),
            'placement_rate': round((stats['total_placed'] / unique_applied * 100), 2) if unique_applied > 0 else 0,
            'placed_students': stats['placed_students']
        })
    
    # Sort companies by total applied
    company_stats_list.sort(key=lambda x: x['total_applied'], reverse=True)
    
    return {
        'overall': {
            'total_students': int(total_students),
            'total_applied': int(total_applied),
            'total_placed': int(total_placed),
            'placement_rate': placement_rate,
            'application_rate': application_rate,
            'selection_rate': selection_rate,
            'avg_applications_per_student': avg_applications
        },
        'funnel': funnel_data,
        'round_pass_rates': round_pass_rate_data,
        'company_stats': company_stats_list,
        'class_stats': {
            'MCA A': {
                'applied': int(len(class_stats['MCA A']['unique_applied'])),
                'placed': int(len(class_stats['MCA A']['placed'])),
                'applications': int(class_stats['MCA A']['total_applications']),
                'placement_rate': round((len(class_stats['MCA A']['placed']) / len(class_stats['MCA A']['unique_applied']) * 100), 2) if len(class_stats['MCA A']['unique_applied']) > 0 else 0
            },
            'MCA B': {
                'applied': int(len(class_stats['MCA B']['unique_applied'])),
                'placed': int(len(class_stats['MCA B']['placed'])),
                'applications': int(class_stats['MCA B']['total_applications']),
                'placement_rate': round((len(class_stats['MCA B']['placed']) / len(class_stats['MCA B']['unique_applied']) * 100), 2) if len(class_stats['MCA B']['unique_applied']) > 0 else 0
            },
            'MSc AIML': {
                'applied': int(len(class_stats['MSc AIML']['unique_applied'])),
                'placed': int(len(class_stats['MSc AIML']['placed'])),
                'applications': int(class_stats['MSc AIML']['total_applications']),
                'placement_rate': round((len(class_stats['MSc AIML']['placed']) / len(class_stats['MSc AIML']['unique_applied']) * 100), 2) if len(class_stats['MSc AIML']['unique_applied']) > 0 else 0
            }
        },
        'student_activity': {
            'total_never_applied': int(total_never_applied),
            'total_active_applicants': int(total_active_applicants),
            'most_active_students': [
                {
                    'name': student_lookup.get(name, {}).get('name', name),
                    'reg_no': student_lookup.get(name, {}).get('reg_no', ''),
                    'class': student_lookup.get(name, {}).get('class', 'Unknown'),
                    'applications': count
                }
                for name, count in most_active_students
            ],
            'least_active_students': [
                {
                    'name': student_lookup.get(name, {}).get('name', name),
                    'reg_no': student_lookup.get(name, {}).get('reg_no', ''),
                    'class': student_lookup.get(name, {}).get('class', 'Unknown'),
                    'applications': count
                }
                for name, count in least_active_students
            ],
            'never_applied_students': never_applied_list[:50]  # Limit to 50 for display
        }
    }

# Get student-wise performance analysis
def get_student_performance_analysis():
    """
    Analyze each student's performance across all companies.
    Shows how far each student progressed in each company they applied to.
    """
    all_analysis = load_all_company_analysis()
    students_df = load_students()
    
    # Create student lookup
    student_lookup = {}
    for _, row in students_df.iterrows():
        name_upper = str(row['Name']).strip().upper()
        student_lookup[name_upper] = {
            'name': row['Name'],
            'reg_no': row['Reg.no'],
            'class': row['Class']
        }
    
    student_performance = {}
    
    # Process each company's data
    for company_id, company_data in all_analysis.items():
        df = company_data['data']
        stages = company_data['stages']
        
        # Find name column
        name_col = None
        for col in df.columns:
            if 'name' in col.lower() and 'student' in col.lower():
                name_col = col
                break
        
        if name_col is None:
            continue
        
        # Process each student
        for _, row in df.iterrows():
            student_name = str(row[name_col]).strip()
            student_name_upper = student_name.upper()
            
            # Find matching student in lookup
            matched_student = None
            for lookup_name, lookup_data in student_lookup.items():
                if lookup_name == student_name_upper:
                    matched_student = lookup_data
                    break
                # Try fuzzy matching
                if student_name_upper in lookup_name or lookup_name in student_name_upper:
                    matched_student = lookup_data
                    break
            
            if not matched_student:
                matched_student = {
                    'name': student_name,
                    'reg_no': row.get('Register Number', 'N/A'),
                    'class': 'Unknown'
                }
            
            # Track student's progress in this company
            student_key = matched_student['name'].upper()
            
            if student_key not in student_performance:
                student_performance[student_key] = {
                    'name': matched_student['name'],
                    'reg_no': matched_student['reg_no'],
                    'class': matched_student['class'],
                    'companies': []
                }
            
            # Get progression through stages (exclude Register Number - it's an identifier, not a round)
            exclude_cols = [name_col, 'Register Number', 'Name', 'Reg.no', 'Reg No']
            stage_columns = [col for col in df.columns if col not in exclude_cols]
            
            progression = []
            last_passed_stage = None
            reached_stage_index = -1
            applied = False
            
            for idx, stage in enumerate(stage_columns):
                if stage in df.columns:
                    value = row.get(stage, 0)
                    # Convert to int if possible
                    if isinstance(value, (int, float)):
                        passed = int(value) == 1
                    else:
                        passed = str(value).strip() == '1'
                    
                    # Track if student applied
                    if 'Applied' in stage or stage == stages[0]:
                        applied = passed
                    
                    if passed:
                        last_passed_stage = stage
                        reached_stage_index = idx
                        progression.append({
                            'stage': stage,
                            'passed': True,
                            'index': idx
                        })
                    else:
                        progression.append({
                            'stage': stage,
                            'passed': False,
                            'index': idx
                        })
            
            # Only add if student actually applied
            if not applied:
                continue
            
            # Determine final status
            if last_passed_stage == 'Selected' or (stages and last_passed_stage == stages[-1] and reached_stage_index == len(stages) - 1):
                status = 'Selected'
            elif last_passed_stage and last_passed_stage != stages[0]:
                status = f'Reached {last_passed_stage}'
            else:
                status = 'Applied Only'
            
            # Count how many stages were actually passed
            stages_passed_count = sum(1 for p in progression if p.get('passed', False))
            
            student_performance[student_key]['companies'].append({
                'company_id': company_id,
                'company_name': company_data['company_name'],
                'progression': progression,
                'last_stage': last_passed_stage,
                'status': status,
                'stages_passed': stages_passed_count,
                'total_stages': len(stages)
            })
    
    # Calculate statistics for each student
    for student_key, student_data in student_performance.items():
        companies = student_data['companies']
        student_data['total_applications'] = len(companies)
        student_data['total_selected'] = sum(1 for c in companies if c['status'] == 'Selected')
        student_data['avg_stages_reached'] = round(sum(c['stages_passed'] for c in companies) / len(companies), 2) if companies else 0
        student_data['max_stages_reached'] = max((c['stages_passed'] for c in companies), default=0)
    
    return student_performance


@app.route('/placement_statistics')
@login_required
def placement_statistics():
    """
    Display overall placement statistics combining ANALYSIS folder and Master_Placement_Fila.csv data.
    """
    return render_template('placement_statistics.html')

@app.route('/api/placement_statistics')
@login_required
def api_placement_statistics():
    """
    Get comprehensive placement statistics combining both data sources.
    """
    try:
        stats = get_comprehensive_placement_statistics()
        return jsonify(stats)
    except Exception as e:
        print(f"Error in placement statistics: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/student_analysis')
@login_required
def student_analysis():
    """
    Display student analysis page with search functionality.
    """
    return render_template('student_analysis.html')

@app.route('/api/student_analysis/<student_name>')
@login_required
def api_student_analysis(student_name):
    """
    Get complete application history for a student.
    """
    try:
        history = get_student_application_history(student_name)
        if history is None:
            return jsonify({'error': 'Student not found'}), 404
        return jsonify(history)
    except Exception as e:
        print(f"Error in student analysis: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/all_students_analysis')
@login_required
def api_all_students_analysis():
    """
    Get analysis for all students - who applies least, who fails at final rounds often, etc.
    """
    try:
        students_df = load_students()
        
        all_students_stats = []
        
        for _, student_row in students_df.iterrows():
            student_name = student_row['Name']
            history = get_student_application_history(student_name)
            
            if history:
                stats = history['statistics']
                all_students_stats.append({
                    'name': student_name,
                    'reg_no': student_row['Reg.no'],
                    'class': student_row['Class'],
                    'total_applications': stats['total_applications'],
                    'total_selected': stats['total_selected'],
                    'failed_at_final': stats['failed_at_final'],
                    'total_reached_final': stats['total_reached_final'],
                    'selection_rate': stats['selection_rate'],
                    'final_round_failure_rate': stats['final_round_failure_rate'],
                    'avg_stages_reached': stats['avg_stages_reached'],
                    'companies_not_applied_count': stats['companies_not_applied_count']
                })
        
        # Sort by different criteria
        least_applications = sorted(all_students_stats, key=lambda x: x['total_applications'])[:20]
        most_final_failures = sorted([s for s in all_students_stats if s['failed_at_final'] > 0], 
                                    key=lambda x: x['failed_at_final'], reverse=True)[:20]
        never_applied = [s for s in all_students_stats if s['total_applications'] == 0]
        
        return jsonify({
            'all_students': all_students_stats,
            'least_applications': least_applications,
            'most_final_failures': most_final_failures,
            'never_applied': never_applied,
            'total_students': len(all_students_stats)
        })
    except Exception as e:
        print(f"Error in all students analysis: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.context_processor
def inject_user_role():
    return dict(
        user_role=session.get('role', None),
        username=session.get('username', None)
    )

if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)
    app.run(debug=True, port=5000)