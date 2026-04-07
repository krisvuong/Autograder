from bs4 import BeautifulSoup
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import datetime as dt
import glob
import os
import pandas as pd
from pathlib import Path
from playwright.sync_api import sync_playwright
import pytest
import yaml
import random
import re
import shutil
import smtplib
import time

from MarkCollector import MarkCollector


with open("config.yaml", "r") as file:
    try:
        config = yaml.safe_load(file)
    except yaml.YAMLError as exc:
        print(f"Error parsing YAML: {exc}")

ASSIGNMENT_NUM = "0"
SUBMISSION_FOLDER = f"submissions/a{ASSIGNMENT_NUM}"
TEST_FILE = f"tests/TestA{ASSIGNMENT_NUM}.py"
OUTPUT_FILE = f"output/a{ASSIGNMENT_NUM}_results.csv"
ASSIGNMENT_NAME = f"Assignment {ASSIGNMENT_NUM}"  # Used as header for grade column in output file
OUTPUT_FOLDER = f"a{ASSIGNMENT_NUM}"
ERROR_FOLDER = f"output/{OUTPUT_FOLDER}_autograde_errors"
LOW_MARK_FOLDER = f"output/{OUTPUT_FOLDER}_low_marks"

SENDER_EMAIL = "xx"
SENDER_APP_PWD = "xx"

def load_mapping(path="mapping.csv"):
    print(f"Reading mapping csv from {path}...")
    return pd.read_csv(path)


def get_latest_submissions():
    # Map: student_id -> latest file
    latest_files = {}

    for file_path in glob.glob(os.path.join(SUBMISSION_FOLDER, "*.py")):
        name_parts = file_path.split(" - ")
        if len(name_parts) < 3:
            continue  # skip malformed names

        student_id = name_parts[0]
        timestamp_str = name_parts[-2]

        # Parse timestamp (assuming format "Sep 10, 2025 317 PM")
        try:
            timestamp_str = re.sub(r'(\d{1,2})(\d{2})\s*([AP]M)', r'\1:\2 \3', timestamp_str)
            timestamp = dt.datetime.strptime(timestamp_str, "%b %d, %Y %I:%M %p")
        except ValueError:
            continue

        # Keep only the latest submission
        if student_id not in latest_files or timestamp > latest_files[student_id][0]:
            latest_files[student_id] = (timestamp, file_path)

    # Return just the file paths
    # return ['submissions/a0/studentid - First Last - Mon DD, YYYY Hmm tt - filename']
    return [fp for ts, fp in latest_files.values()]


def run_tests(student_file, name, output_html):
    print("Running unit tests...")
    collector = MarkCollector()
    try:
        pytest.main([
            TEST_FILE,
            f"--submission_path={student_file}",
            "-vv",
            "-rfp",
            "--html=output.html",
            "--self-contained-html",
            f'--report-title={ASSIGNMENT_NAME} Results - {name}',
            "--tb=short",
        ], plugins=[collector])
    except Exception as e:
        print(f"Error running tests for {name}: {e}")
        raise e
    print("passed:", collector.passed)
    print("partial passes:", collector.partial)
    print("collected:", collector.collected)
    return (collector.passed + 0.5 * collector.partial) / collector.collected * 100


def html_to_pdf(input_html, output_pdf):
    input_html = str(Path(input_html).resolve())
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"file://{input_html}")
        page.pdf(path=output_pdf, format="A4")
        browser.close()


def get_student_info(key, mapping, filter_by="NAME"):
    if filter_by == "NAME":
        matches = mapping[(mapping['First Name'] + " " + mapping['Last Name']) == key]
    else:  # filter by MACID
        matches = mapping[mapping['Username'] == f"#{key}"]

    if matches.empty:
        raise ValueError(f"No student found in mapping.csv for {key}")
    elif len(matches) > 1:
        raise ValueError(f"Multiple rows found in mapping.csv for: {key}")
    else:
        print(f"Found info for {key}")
        return matches


def create_results_csv(filename=None):
    if not filename:
        filename = f"results_{str(dt.datetime.now().strftime("%Y_%m_%d_%H_%M_%S"))}.csv"
    df = pd.DataFrame(columns=["OrgDefinedId", "Username", f"{ASSIGNMENT_NAME} Points Grade", "End-of-Line Indicator"])
    df.to_csv(filename, index=False)


def write_result_to_csv(filename, result_df):
    result_df.to_csv(filename, index=False, mode="a", header=False)


def get_name_from_filename(filename: str):
    filename = filename.split("/")[-1]  # Remove leading directories
    name = filename.split(' - ')[1]
    return name


def send_email(name, recipient_email, attachment_path, server):
    subject = f"{ASSIGNMENT_NAME} Feedback"
    body = f"""Hello {name},

    See the attached file for your feedback on {ASSIGNMENT_NAME}.
    """
    with open(attachment_path, "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())
    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        f"attachment; filename= {attachment_path}",
    )
    message = MIMEMultipart()
    message['Subject'] = subject
    message['From'] = SENDER_EMAIL
    message['To'] = recipient_email
    html_part = MIMEText(body)
    message.attach(html_part)
    message.attach(part)

    server.sendmail(SENDER_EMAIL, recipient_email, message.as_string())

    print("Message sent!")


def get_output_pdfs():
    folder = f"output/{OUTPUT_FOLDER}"
    return glob.glob(os.path.join(folder, "*.pdf"))
    

def try_send_email(filepaths):
    error_emails = []
    mapping = load_mapping("mapping.csv")

    # extract name and email from pdf name
    print(f"Found {len(filepaths)} feedback pdfs to send...")
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(SENDER_EMAIL, SENDER_APP_PWD)
        for i, fp in enumerate(filepaths):
            time.sleep(random.uniform(2, 6))  # Random delay to avoid spam filters
            print(f"Sending email {i+1}/{len(filepaths)}...")
            try:
                mac_id = fp.split("/")[-1].split("_")[-1].replace(".pdf", "")
                student_info = get_student_info(mac_id, mapping, filter_by="MACID")
                name = student_info.iloc[0]['First Name']
                email = f"{mac_id}@mcmaster.ca"
                send_email(name, email, fp, server)
            except Exception as e:
                print(f"Error sending email to {email}: {e}")
                error_emails.append((name, email, mac_id, fp))
        
    return error_emails
    

def release_grades(only_try_errors=False):
    if only_try_errors:  # Only send emails that previously failed
        filepaths = pd.read_csv(f"output/{OUTPUT_FOLDER}_email_errors.csv")
        filepaths = filepaths['filepath'].tolist()
        error_emails = try_send_email(filepaths=filepaths)
    else:  # Send all emails
        error_emails = try_send_email(filepaths=get_output_pdfs())

    if len(error_emails) > 0:
        print(f"{len(error_emails)} emails could not be sent. See output folder for details.")
        with open(f"output/{OUTPUT_FOLDER}_email_errors.csv", "w") as f:
            f.write("name,email,mac_id,filepath\n")
            for name, email, mac_id, fp in error_emails:
                f.write(f"{name},{email},{mac_id},{fp}\n")
    else:
        print(f"All {len(error_emails)} emails sent successfully!")


def add_custom_feedback(input_html, student_file, mac_id):

    custom_feedback = {
        "macid": "feedback"
    }
    if mac_id not in custom_feedback:
        return
    # Read the file
    with open(input_html, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
    # Create a new <p> element for the message
    note_tag = soup.new_tag("p")
    note_tag.string = custom_feedback[mac_id]
    note_tag["style"] = "color:red; font-weight:bold;"
    # Find a good place to insert - below the summary section or at end of <body>
    summary_div = soup.find("div", {"class": "summary"})
    if summary_div:
        summary_div.append(note_tag)
    else:
        # Fallback - append to end of <body>
        soup.body.append(note_tag)
    # Save the modified HTML
    with open(input_html, "w", encoding="utf-8") as f:
        f.write(str(soup))
    print(f"Custom message successfully added for {mac_id}!")


def generate_feedback():
    """
    Run tests from TEST_FILE on each submission in SUBMISSION_FOLDER.
    Generate output CSV with results that can be uploaded to Avenue.
    Generate individual PDF feedback files for each student.
    Save error submissions and low-mark submissions to separate folders for manual review.
    """
    mapping = load_mapping("mapping.csv")
    submissions = get_latest_submissions()
    create_results_csv(OUTPUT_FILE)

    if os.path.exists(f"output/{OUTPUT_FOLDER}"):
        shutil.rmtree(f"output/{OUTPUT_FOLDER}")
    os.makedirs(f"output/{OUTPUT_FOLDER}")

    error_submissions = []
    low_mark_submissions = []

    for s in submissions:
        try:
            name = get_name_from_filename(s)
            result_df = get_student_info(name, mapping, "NAME")
            test_result = run_tests(s, name, "output.html")
            mac_id = str(result_df.iloc[0]['Username']).replace("#", "")
            add_custom_feedback("output.html", s, mac_id)
            output_pdf_name = f"output/{OUTPUT_FOLDER}/{OUTPUT_FOLDER}_{mac_id}.pdf"
            html_to_pdf("output.html", output_pdf_name)
            result_df[f"{ASSIGNMENT_NAME} Points Grade"] = test_result
            result_df["End-of-Line Indicator"] = "#"
            result_df = result_df.drop(["Last Name", "First Name", "Email"], axis=1)  # Fornmat for Avenue upload
            write_result_to_csv(OUTPUT_FILE, result_df)

            # Flag low-mark submissions for manual review
            if test_result <= 50.0:
                print(f"Low mark ({test_result}%) for {name}")
                low_mark_submissions.append((s, output_pdf_name))
        except Exception as e:
            print(f"Error occured while grading submission {s}: {e}")
            print(f"Skipping to next submission...")
            # Flag error submissions for manual review
            error_submissions.append((s, e))


    # Copy error submissions to error folder
    if os.path.exists(ERROR_FOLDER):
        shutil.rmtree(ERROR_FOLDER)
    if len(error_submissions) > 0:
        print(f"Copying {len(error_submissions)} error submissions to {ERROR_FOLDER}...")

        # Delete and recreate directory
        os.makedirs(ERROR_FOLDER)

        for s, _ in error_submissions:
            src = s
            dst = f"{ERROR_FOLDER}/{s.split('/')[-1]}"
            shutil.copy(src, dst)

    # Delete low mark folder
    if os.path.exists(LOW_MARK_FOLDER):
        shutil.rmtree(LOW_MARK_FOLDER)
    # Copy low-mark submissions to error folder
    if len(low_mark_submissions) > 0:
        print(f"Copying {len(low_mark_submissions)} low-mark submissions to {LOW_MARK_FOLDER}...")

        os.makedirs(LOW_MARK_FOLDER)

        for (submission, output_pdf) in low_mark_submissions:
            dst = f"{LOW_MARK_FOLDER}/{os.path.basename(submission)}"
            shutil.copy(submission, dst)  # TODO: move instead of copy, so we can just make edits and move back
            dst = f"{LOW_MARK_FOLDER}/{os.path.basename(output_pdf)}"
            shutil.copy(output_pdf, dst)


    result_csv = pd.read_csv(OUTPUT_FILE)
    print(f"{len(mapping)} students in the class")
    print(f"{len(submissions)} students made a submission")
    print(f"{len(result_csv)} grades recorded in result csv")
    print(f"{len(error_submissions)} error submissions (could not mark):")
    for s, e in error_submissions:
        print(f" - {s}")
        print(f"   Due to: {e}")
    print(f"{len(low_mark_submissions)} submissions with <= 50.0%:")
    for s in low_mark_submissions:
        print(f" - {s}")
    
    print()
    print("==========================================================")
    print("========================= STATS ==========================")
    print("==========================================================")
    print()

    print(f"Statistics for students that made a submission:")
    grades = result_csv[f"{ASSIGNMENT_NAME} Points Grade"]
    print(f" - Mean: {grades.mean()}")
    print(f" - Median: {grades.median()}")
    print(f" - Mode: {grades.mode()[0]}")
    print(f" - Stdev: {grades.std()}")
    print(f" - Min: {grades.min()}")
    print(f" - Max: {grades.max()}")


if __name__ == "__main__":
    generate_feedback()
    # release_grades(only_try_errors=False)
    # release_grades(only_try_errors=True)
