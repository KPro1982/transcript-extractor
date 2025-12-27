# Sample Q/A Extraction Diagnostic Log

This is an example of what the comprehensive Q/A test log looks like after the refactor.

```
================================================================================
Q/A EXTRACTION DIAGNOSTIC REPORT
================================================================================

SECTION 1: TEST CONFIGURATION
--------------------------------------------------------------------------------

Document ID: 12345678-abcd-1234-5678-123456789abc
Test Range: Pages 5 - 150
Max Q/A Pairs: 10

Question Patterns:
  - Q. (with optional middle dots): ^[·\s]*Q\.[·\s]*
  - Q. (standard): ^\s*Q\.\s*
  - Q: (colon format): ^\s*Q:\s*
  - Q (space + capital): ^Q\s+[A-Z]
  - QUESTION:: ^\s*QUESTION[:\s]+
  - BY MR./MS. NAME:: ^BY\s+M[RS]\.\s+\w+:

Answer Patterns:
  - A. (with optional middle dots): ^[·\s]*A\.[·\s]*
  - A. (standard): ^\s*A\.\s*
  - A: (colon format): ^\s*A:\s*
  - A (space + capital): ^A\s+[A-Z]
  - ANSWER:: ^\s*ANSWER[:\s]+
  - THE WITNESS:: ^[·\s]*THE\s+WITNESS:[·\s]*

================================================================================

SECTION 2: TEXT EXTRACTION DIAGNOSTICS
--------------------------------------------------------------------------------

Pages Analyzed: 20
Total Lines: 1847
Non-Empty Lines: 1623
Average Line Length: 42.3 characters

Sample Text (First 3 Pages, First 30 Lines):

--- PAGE 5 ---
  1| 
  2|                    EXAMINATION
  3| 
  4| BY MR. JOHNSON:
  5|      Q.    Good morning, Dr. Smith. Can you please
  6| state your full name for the record?
  7|      A.    My name is Dr. Robert James Smith.
  8|      Q.    And what is your current occupation?
  9|      A.    I am a forensic pathologist at Memorial
 10| Hospital.
 11|      Q.    How long have you been in that position?
 12|      A.    I've been working there for approximately
 13| 15 years.
 14|      Q.    Can you describe your educational
 15| background?
 16|      A.    I received my medical degree from Harvard
 17| Medical School in 1995, and completed my residency
 18| in pathology at Johns Hopkins Hospital.
 19|      Q.    Are you board certified?
 20|      A.    Yes, I am board certified in anatomic and
 21| clinical pathology.
 22|      Q.    Have you testified as an expert witness
 23| before?
 24|      A.    Yes, I have testified in approximately 50
 25| cases over the past 10 years.
 26|      Q.    Now, turning to the case at hand, when did
 27| you first become involved?
 28|      A.    I was contacted by the district attorney's
 29| office in March 2023.
 30|      Q.    What were you asked to do?

--- PAGE 6 ---
  1|      A.    I was asked to review the autopsy report
  2| and provide an independent opinion on the cause of
  3| death.
  4|      Q.    Did you conduct a physical examination of
  5| the body?
  6|      A.    No, I only reviewed the existing
  7| documentation, including photographs, X-rays, and the
  8| original autopsy report.
  9|      Q.    What materials did you review?
 10|      A.    I reviewed approximately 200 pages of
 11| medical records, the complete autopsy report, 
 12| toxicology results, and crime scene photographs.
 13|      Q.    How much time did you spend on this review?
 14|      A.    I spent approximately 40 hours reviewing
 15| all the materials and preparing my report.

================================================================================

SECTION 3: PATTERN MATCHING ANALYSIS
--------------------------------------------------------------------------------

Question Patterns Matched: 87
Answer Patterns Matched: 85
Lines With No Match: 1451

Question Pattern Usage:
  - Q. (with optional middle dots): 65 matches
  - BY MR./MS. NAME:: 22 matches

Answer Pattern Usage:
  - A. (with optional middle dots): 73 matches
  - THE WITNESS:: 12 matches

Sample Question Matches (First 5):
  Page 5, Line 5: [Q. (with optional middle dots)] Q.    Good morning, Dr. Smith. Can you please
  Page 5, Line 8: [Q. (with optional middle dots)] Q.    And what is your current occupation?
  Page 5, Line 11: [Q. (with optional middle dots)] Q.    How long have you been in that position?
  Page 5, Line 14: [Q. (with optional middle dots)] Q.    Can you describe your educational
  Page 5, Line 19: [Q. (with optional middle dots)] Q.    Are you board certified?

Sample Answer Matches (First 5):
  Page 5, Line 7: [A. (with optional middle dots)] A.    My name is Dr. Robert James Smith.
  Page 5, Line 9: [A. (with optional middle dots)] A.    I am a forensic pathologist at Memorial
  Page 5, Line 12: [A. (with optional middle dots)] A.    I've been working there for approximately
  Page 5, Line 16: [A. (with optional middle dots)] A.    I received my medical degree from Harvard
  Page 5, Line 20: [A. (with optional middle dots)] A.    Yes, I am board certified in anatomic and

Sample Lines With No Pattern Match (First 10):
  Page 5, Line 2: EXAMINATION
  Page 5, Line 4: BY MR. JOHNSON:
  Page 5, Line 6: state your full name for the record?
  Page 5, Line 10: Hospital.
  Page 5, Line 13: 15 years.
  Page 5, Line 15: background?
  Page 5, Line 17: Medical School in 1995, and completed my residency
  Page 5, Line 18: in pathology at Johns Hopkins Hospital.
  Page 5, Line 21: clinical pathology.
  Page 5, Line 22: before?

================================================================================

SECTION 4: LINE-BY-LINE ANALYSIS (First 100 Lines)
--------------------------------------------------------------------------------
Page   Line   State        Class                Pattern                        Text
--------------------------------------------------------------------------------
5      1      searching    EMPTY                                               
5      2      searching    UNKNOWN                                             EXAMINATION
5      3      searching    EMPTY                                               
5      4      searching    UNKNOWN                                             BY MR. JOHNSON:
5      5      searching    QUESTION             Q. (with optional middle dots) Q.    Good morning, Dr. Smith. Can you please
5      6      in_question  CONTINUATION (question)                             state your full name for the record?
5      7      in_question  ANSWER               A. (with optional middle dots) A.    My name is Dr. Robert James Smith.
5      8      in_answer    QUESTION             Q. (with optional middle dots) Q.    And what is your current occupation?
5      9      in_question  ANSWER               A. (with optional middle dots) A.    I am a forensic pathologist at Memorial
5      10     in_answer    CONTINUATION (answer)                               Hospital.
5      11     in_answer    QUESTION             Q. (with optional middle dots) Q.    How long have you been in that position?
5      12     in_question  ANSWER               A. (with optional middle dots) A.    I've been working there for approximately
5      13     in_answer    CONTINUATION (answer)                               15 years.
5      14     in_answer    QUESTION             Q. (with optional middle dots) Q.    Can you describe your educational
5      15     in_question  CONTINUATION (question)                             background?
5      16     in_question  ANSWER               A. (with optional middle dots) A.    I received my medical degree from Harvard
5      17     in_answer    CONTINUATION (answer)                               Medical School in 1995, and completed my residency
5      18     in_answer    CONTINUATION (answer)                               in pathology at Johns Hopkins Hospital.

================================================================================

SECTION 5: EXTRACTION STATE MACHINE
--------------------------------------------------------------------------------

State Transitions: 34
Incomplete Q/A Pairs: 2

State Transitions (First 20):
  Page 5, Line 5: searching -> in_question (Question pattern matched: Q. (with optional middle dots))
  Page 5, Line 7: in_question -> in_answer (Answer pattern matched: A. (with optional middle dots))
  Page 5, Line 8: in_answer -> in_question (Question pattern matched: Q. (with optional middle dots))
  Page 5, Line 9: in_question -> in_answer (Answer pattern matched: A. (with optional middle dots))
  Page 5, Line 11: in_answer -> in_question (Question pattern matched: Q. (with optional middle dots))
  Page 5, Line 12: in_question -> in_answer (Answer pattern matched: A. (with optional middle dots))
  Page 5, Line 14: in_answer -> in_question (Question pattern matched: Q. (with optional middle dots))
  Page 5, Line 16: in_question -> in_answer (Answer pattern matched: A. (with optional middle dots))
  Page 5, Line 19: in_answer -> in_question (Question pattern matched: Q. (with optional middle dots))
  Page 5, Line 20: in_question -> in_answer (Answer pattern matched: A. (with optional middle dots))

Incomplete Q/A Pairs:
  question_without_answer - Page 24, Line 15
    Text: Q.    Let me ask you about the timeline. When exactly did you first notic

================================================================================

SECTION 6: RESULTS SUMMARY
--------------------------------------------------------------------------------

Q/A Pairs Extracted: 10

SAMPLE Q/A PAIRS:

PAIR 1 (Page 5, Line 5)
================================================================================
QUESTION: Q.    Good morning, Dr. Smith. Can you please state your full name for the record?

ANSWER: A.    My name is Dr. Robert James Smith.
--------------------------------------------------------------------------------

PAIR 2 (Page 5, Line 8)
================================================================================
QUESTION: Q.    And what is your current occupation?

ANSWER: A.    I am a forensic pathologist at Memorial Hospital.
--------------------------------------------------------------------------------

PAIR 3 (Page 5, Line 11)
================================================================================
QUESTION: Q.    How long have you been in that position?

ANSWER: A.    I've been working there for approximately 15 years.
--------------------------------------------------------------------------------

DIAGNOSTIC CONCLUSIONS:
  - SUCCESS: 10 Q/A pairs extracted successfully
  - Most common question pattern: Q. (with optional middle dots) (65 matches)
  - Most common answer pattern: A. (with optional middle dots) (73 matches)
  - WARNING: 2 questions without answers

RECOMMENDATIONS:
  - Some questions may be followed by other questions without answers

================================================================================
DIAGNOSTIC REPORT COMPLETE
================================================================================
```

## How to Access the Log in Your Application

1. **Upload a PDF** through the frontend
2. After upload completes, go to the **Select Pages** page
3. You should see the **"View Q/A Test Log"** button at the top of the page range section
4. Click the button to view the comprehensive diagnostic log in a modal

## What Each Section Shows

- **Section 1**: Configuration and patterns being used
- **Section 2**: Raw text samples from the PDF (helps identify format issues)
- **Section 3**: Which patterns matched, how often, and sample text
- **Section 4**: Line-by-line breakdown showing state machine behavior
- **Section 5**: State transitions and any incomplete Q/A pairs
- **Section 6**: Final results with diagnostic conclusions and recommendations

This log will help you diagnose:
- Text extraction issues (if PDF is scanned/corrupted)
- Pattern matching failures (if transcript uses non-standard format)
- State machine problems (if Q/A pairs aren't forming correctly)

