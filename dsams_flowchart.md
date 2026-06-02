# DSAMS (Departmental Student Attendance Monitoring System) Flowchart

This report contains the core system workflow flowchart for the DSAMS project. It visualizes the step-by-step logic and decision paths based on the primary user roles (Teaching Staff, HOD, and Student) and highlights the key functionalities such as session management and attendance tracking.

## Core System Workflow Flowchart

The following diagram maps out the user journey from login through the specific workflows designated for each role.

```mermaid
flowchart TD
    %% Styling
    classDef default fill:#f9f9f9,stroke:#333,stroke-width:1px
    classDef decision fill:#fff3cd,stroke:#ffeeba,stroke-width:2px,color:#856404
    classDef process fill:#d1ecf1,stroke:#bee5eb,stroke-width:2px,color:#0c5460
    classDef termination fill:#f8d7da,stroke:#f5c6cb,stroke-width:2px,color:#721c24
    classDef startend fill:#d4edda,stroke:#c3e6cb,stroke-width:2px,color:#155724

    %% Diagram Logic
    Start([System Access]):::startend --> Login[User Authentication]:::process
    Login --> RoleCheck{Determine User Role}:::decision
    
    %% ========================================
    %% Teaching Staff Workflow
    %% ========================================
    RoleCheck -->|Teaching Staff| LecDash[Teaching Staff Dashboard]:::process
    LecDash --> ViewSessions[View Assigned Timetable]:::process
    ViewSessions --> SessionPreWindow{Is it within 0-30m\npre-session window?}:::decision
    
    %% Teaching Staff Actions
    SessionPreWindow -->|Yes| ActionDecision{Teaching Staff Action}:::decision
    ActionDecision -->|Confirm| SessionConfirmed[Status: LECTURER_CONFIRMED]:::process
    ActionDecision -->|Cancel| SessionCancelled[Status: CANCELLED]:::termination
    ActionDecision -->|Reschedule| SessionRescheduled[Status: RESCHEDULED]:::process
    
    %% Auto-Monitoring
    SessionPreWindow -->|No interaction\nafter 45m| AutoMiss[Auto-marked as MISSED]:::termination
    
    %% Notifications trigger
    SessionCancelled & SessionRescheduled & AutoMiss --> TriggerAlerts[Trigger Alert Service:\nNotify Students & Coordinator]:::process
    
    %% Attendance flow
    SessionConfirmed --> ClassOccurs[Conduct Scheduled Lecture]:::process
    ClassOccurs --> SubmitAttn[Submit Attendance Record]:::process
    SubmitAttn --> WaitApproval(Pending HOD Review)
    
    %% ========================================
    %% HOD Workflow
    %% ========================================
    RoleCheck -->|HOD| HODDash[HOD Executive Dashboard]:::process
    HODDash --> HODAction{Select Dashboard Action}:::decision
    
    HODAction -->|Review Overdue| HandleMissed[Process MISSED / Auto-Confirmed Sessions]:::process
    HODAction -->|View Analytics| ViewReports[Generate & Export Overview Reports]:::process
    HODAction -->|Review Attendance| ApproveAttn[Approve or Reject Submitted Attendance]:::process
    ApproveAttn -->|Approved| AttnFinalized[Attendance Finalized in System]:::process
    ApproveAttn -->|Rejected| WaitApproval
    
    %% ========================================
    %% Student Workflow
    %% ========================================
    RoleCheck -->|Student| StudentDash[Student Dashboard]:::process
    StudentDash --> ViewStats[Review Personal Attendance Percentage]:::process
    StudentDash --> ViewTimetable[View Course Timetable & Alerts]:::process

    %% ========================================
    %% Workflow Conclusion
    %% ========================================
    AttnFinalized & TriggerAlerts & HandleMissed & ViewReports & ViewStats & ViewTimetable --> End([End Workflow Cycle]):::startend
```

### Flowchart Breakdown

1. **Authentication:** The workflow begins when a user logs in. The system immediately routes the user to a specific dashboard tailored to their administrative role.
2. **Teaching Staff Mechanics:** 
   * **Pre-Session Management:** Prior to a lecture, teaching staff are prompted to confirm, cancel, or propose a reschedule for the class.
   * **Automated Oversight:** If teaching staff fail to confirm a session within 45 minutes of its scheduled start time, the system will actively bypass intervention and flag the session as `MISSED`.
   * **Communication:** Any canceled, rescheduled, or missed sessions automatically trigger the **Alert Service** to warn students and dispatch updates to the HOD/Coordinator.
   * **Attendance Capture:** Only fully confirmed sessions transition to allow the capture of student attendance, which is then batched for head-of-department review.
3. **HOD Mechanics:** Head of Departments overview the generated data, focusing on resolving anomalies (missed sessions) or systematically approving finalized attendance rosters submitted by their staff.
4. **Student Mechanics:** The end-user primarily utilizes the system as a real-time monitor for their aggregated attendance rates and timetable adjustments stemming from teaching staff decisions.
