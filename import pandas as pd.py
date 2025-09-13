import pandas as pd
import os

# Change to your Downloads directory
os.chdir(os.path.expanduser('~/Downloads'))
# Load the fees file
fees = pd.read_csv("fees.csv")

# Generate parent email from student_name
fees["parent_email"] = fees["student_name"].str.lower().str.replace(" ", ".") + ".p@school.com"

# Save back
fees.to_csv("fees.csv", index=False)
print(fees.head())
