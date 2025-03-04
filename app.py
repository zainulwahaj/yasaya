from flask import Flask, request, render_template, jsonify, send_file, session
import pandas as pd
import random
from io import BytesIO

app = Flask(__name__)
app.secret_key = "YOUR_SECRET_KEY"  # Needed for session usage

# Global cache in case session data is lost (for demo purposes)
schedule_cache = None

def process_schedule(courses_file, rooms_file, teachers_file):
    # ================== Read Excel files ==================
    courses_df = pd.read_excel(
        courses_file,
        usecols=[
            'Course Code',
            'Course Name',
            'Department Name',
            'Class Name',
            'Number Of Students',
            'Semester'
        ]
    )
    rooms_df = pd.read_excel(
        rooms_file,
        usecols=['Room ID', 'Room Name', 'Room Capacity', 'Type']
    ).drop_duplicates()
    teachers_df = pd.read_excel(
        teachers_file,
        usecols=['Teacher ID', 'Teacher Name', 'Teacher Designation', 'Number of Duties']
    ).drop_duplicates()
    
    # ================== Step 1: Group courses & sort ==================
    grouped_courses_df = (
        courses_df
        .groupby(['Course Code', 'Course Name', 'Department Name', 'Class Name', 'Semester'], dropna=False)
        .agg({'Number Of Students': 'sum'})
        .reset_index()
        .drop_duplicates()
        .sort_values(by='Number Of Students', ascending=False)
    )
    
    # ================== Step 2: Date-timeslot combos ==================
    dates = ['2024-10-28', '2024-10-29', '2024-10-30', '2024-10-31', '2024-11-01', '2024-11-02']
    timeslots = ['8:30 - 09:50', '10:00 - 11:20', '11:30 - 12:50', '1:00 - 2:20', '2:30 - 3:50', '4:00 - 5:20']
    dates_df = pd.DataFrame(dates, columns=['Date'])
    timeslots_df = pd.DataFrame(timeslots, columns=['Timeslot'])
    dates_timeslots_df = dates_df.merge(timeslots_df, how='cross')
    date_timeslot_list = dates_timeslots_df.to_dict('records')
    random.shuffle(date_timeslot_list)
    
    # ================== Step 3: Predefined course->timeslot map ==================
    course_date_timeslot_mapping = {
        'HUM102': ('2024-10-29', '8:30 - 09:50'),
        'HUM112 /HUM116': ('2024-10-30', '8:30 - 09:50'),
        'HUM112 / HUM110': ('2024-10-30', '8:30 - 09:50'),
        'HUM113 / HUM111': ('2024-10-31', '8:30 - 09:50'),
        'HUM113 / Pakistan Studies': ('2024-11-01', '8:30 - 09:50'),
        'HUM122': ('2024-11-01', '8:30 - 09:50'),
    }
    
    department_semester_tracker = {}
    
    def refill_date_timeslot_list():
        nonlocal date_timeslot_list
        if not date_timeslot_list:
            date_timeslot_list = dates_timeslots_df.to_dict('records')
            random.shuffle(date_timeslot_list)
    
    def assign_dates_timeslots(df):
        course_date_tracker = {}
        dept_sem_tracker = {}
        
        # 3a. First assign predefined timeslots
        for idx, row in df.iterrows():
            course_code = row['Course Code']
            dept_sem_key = (row['Department Name'], row['Semester'])
            if course_code in course_date_timeslot_mapping:
                assigned_date, assigned_timeslot = course_date_timeslot_mapping[course_code]
                if (
                    dept_sem_key not in department_semester_tracker
                    or assigned_date not in department_semester_tracker[dept_sem_key]
                ):
                    department_semester_tracker.setdefault(dept_sem_key, []).append(assigned_date)
                    df.at[idx, 'Date'] = assigned_date
                    df.at[idx, 'Timeslot'] = assigned_timeslot
        
        # 3b. Then assign remaining courses
        for idx, row in df.iterrows():
            course_group_key = (
                row['Course Code'],
                row['Course Name'],
                row['Department Name'],
                row['Semester']
            )
            dept_sem_key = (row['Department Name'], row['Semester'])
            
            # Skip if predefined date/timeslot already assigned
            if pd.notna(row.get('Date')) and pd.notna(row.get('Timeslot')):
                continue
            
            if course_group_key in course_date_tracker:
                assigned_date, assigned_timeslot = course_date_tracker[course_group_key]
            else:
                assigned_date_timeslot = None
                while date_timeslot_list:
                    dt = date_timeslot_list.pop(0)
                    if (
                        dept_sem_key not in dept_sem_tracker
                        or dt['Date'] not in dept_sem_tracker[dept_sem_key]
                    ):
                        assigned_date_timeslot = dt
                        break
                if not assigned_date_timeslot:
                    refill_date_timeslot_list()
                    dt = date_timeslot_list.pop(0)
                    assigned_date_timeslot = dt
                
                assigned_date = assigned_date_timeslot['Date']
                assigned_timeslot = assigned_date_timeslot['Timeslot']
                course_date_tracker[course_group_key] = (assigned_date, assigned_timeslot)
                dept_sem_tracker.setdefault(dept_sem_key, []).append(assigned_date)
            
            df.at[idx, 'Date'] = assigned_date
            df.at[idx, 'Timeslot'] = assigned_timeslot
        
        return df
    
    grouped_courses_df = assign_dates_timeslots(grouped_courses_df)
    
    # ================== Step 4: Room allocation ==================
    def allocate_rooms(df1, df2):
        df2 = df2.sort_values(by='Room Capacity', ascending=False)
        rooms_list = df2.to_dict('records')
        
        allocated_rooms = []
        room_capacity_tracker = {}
        
        for _, course in df1.iterrows():
            num_students = course['Number Of Students']
            course_code = course['Course Code']
            course_name = course['Course Name']
            department_name = course['Department Name']
            semester = course['Semester']
            date = course['Date']
            timeslot = course['Timeslot']
            
            date_timeslot_key = (date, timeslot)
            if date_timeslot_key not in room_capacity_tracker:
                room_capacity_tracker[date_timeslot_key] = {
                    room['Room Name']: room['Room Capacity'] for room in rooms_list
                }
            
            for room in rooms_list:
                room_name = room['Room Name']
                full_capacity = room['Room Capacity']
                remaining_capacity = room_capacity_tracker[date_timeslot_key][room_name]
                half_capacity = full_capacity // 2
                
                if remaining_capacity >= half_capacity:
                    students_to_allocate = min(num_students, half_capacity)
                    
                    allocated_rooms.append({
                        'Date': date,
                        'Timeslot': timeslot,
                        'Course Code': course_code,
                        'Course Name': course_name,
                        'Semester': semester,
                        'Department Name': department_name,
                        'Class Name': course['Class Name'],
                        'Room Name': room_name,
                        'Number of Students Allocated': students_to_allocate,
                        'Room Capacity': full_capacity
                    })
                    
                    room_capacity_tracker[date_timeslot_key][room_name] -= students_to_allocate
                    num_students -= students_to_allocate
                    
                    if num_students == 0:
                        break
        
        allocated_rooms_df = pd.DataFrame(allocated_rooms)
        allocated_rooms_df = allocated_rooms_df[[
            'Date', 'Timeslot', 'Course Code', 'Course Name', 'Semester',
            'Department Name', 'Class Name', 'Room Name',
            'Number of Students Allocated', 'Room Capacity'
        ]]
        return allocated_rooms_df
    
    df3 = allocate_rooms(grouped_courses_df, rooms_df)
    
    # ================== Step 5: Teacher allocation ==================
    def allocate_teachers(df3, teachers_df):
        available_teachers_df = teachers_df[teachers_df['Number of Duties'] > 0].copy()
        teacher_duties_tracker = dict(
            zip(available_teachers_df['Teacher Name'], available_teachers_df['Number of Duties'])
        )
        
        unique_combinations = df3[['Date', 'Timeslot', 'Room Name']].drop_duplicates()
        teacher_allocations = []
        
        for _, combo in unique_combinations.iterrows():
            date = combo['Date']
            timeslot = combo['Timeslot']
            room_name = combo['Room Name']
            
            teacher_1 = None
            teacher_2 = None
            
            available_teachers = available_teachers_df['Teacher Name'].tolist()
            random.shuffle(available_teachers)
            
            for teacher in available_teachers:
                if teacher_duties_tracker.get(teacher, 0) > 0:
                    if not teacher_1:
                        teacher_1 = teacher
                    elif teacher != teacher_1:
                        teacher_2 = teacher
                        break
            
            if teacher_1:
                teacher_duties_tracker[teacher_1] -= 1
                teacher_allocations.append({
                    'Date': date,
                    'Timeslot': timeslot,
                    'Room Name': room_name,
                    'Teacher Name': teacher_1,
                    'Duty Type': 'Teacher Duty 1'
                })
            else:
                teacher_allocations.append({
                    'Date': date,
                    'Timeslot': timeslot,
                    'Room Name': room_name,
                    'Teacher Name': 'No Teacher Available',
                    'Duty Type': 'Teacher Duty 1'
                })
            
            if teacher_2:
                teacher_duties_tracker[teacher_2] -= 1
                teacher_allocations.append({
                    'Date': date,
                    'Timeslot': timeslot,
                    'Room Name': room_name,
                    'Teacher Name': teacher_2,
                    'Duty Type': 'Teacher Duty 2'
                })
            else:
                teacher_allocations.append({
                    'Date': date,
                    'Timeslot': timeslot,
                    'Room Name': room_name,
                    'Teacher Name': 'No Teacher Available',
                    'Duty Type': 'Teacher Duty 2'
                })
        
        teacher_allocations_df = pd.DataFrame(teacher_allocations)
        
        df3 = pd.merge(
            df3,
            teacher_allocations_df.loc[teacher_allocations_df['Duty Type'] == 'Teacher Duty 1',
                                       ['Date', 'Timeslot', 'Room Name', 'Teacher Name']],
            on=['Date', 'Timeslot', 'Room Name'],
            how='left'
        ).rename(columns={'Teacher Name': 'Teacher 1'})
        
        df3 = pd.merge(
            df3,
            teacher_allocations_df.loc[teacher_allocations_df['Duty Type'] == 'Teacher Duty 2',
                                       ['Date', 'Timeslot', 'Room Name', 'Teacher Name']],
            on=['Date', 'Timeslot', 'Room Name'],
            how='left'
        ).rename(columns={'Teacher Name': 'Teacher 2'})
        
        return df3, teacher_allocations_df
    
    df3, teacher_duties_df = allocate_teachers(df3, teachers_df)
    
    return df3, teacher_duties_df

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    global schedule_cache
    try:
        if (
            'courseFile' not in request.files or
            'roomFile' not in request.files or
            'teacherFile' not in request.files
        ):
            return jsonify({"error": "Please upload all required files."}), 400
        
        course_file = request.files['courseFile']
        room_file = request.files['roomFile']
        teacher_file = request.files['teacherFile']
        
        final_schedule_df, teacher_duties_df = process_schedule(course_file, room_file, teacher_file)
        
        # Convert DataFrames to list-of-dicts (handling NaNs) for session storage
        schedule_data = final_schedule_df.where(pd.notnull(final_schedule_df), None).to_dict(orient='records')
        duties_data = teacher_duties_df.where(pd.notnull(teacher_duties_df), None).to_dict(orient='records')
        
        # Store in session and update global cache
        session['schedule_data'] = schedule_data
        session['teacher_duties_data'] = duties_data
        schedule_cache = schedule_data
        
        return jsonify({"schedule": schedule_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/download_csv', methods=['GET'])
def download_csv():
    # Try session first; if missing, then check the global cache.
    schedule_data = session.get('schedule_data') or schedule_cache
    if not schedule_data:
        return "No schedule found in session. Generate the schedule first.", 400
    
    df_schedule = pd.DataFrame(schedule_data)
    output = BytesIO()
    df_schedule.to_csv(output, index=False)
    output.seek(0)
    
    return send_file(
        output,
        mimetype='text/csv',
        download_name='ExamSchedule.csv',
        as_attachment=True
    )

if __name__ == '__main__':
    app.run(debug=True)
