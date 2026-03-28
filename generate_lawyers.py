import csv
import random

names = ["Rahul", "Anita", "Arjun", "Priya", "Vikram", "Sneha", "Rohit", "Kavya", "Manoj", "Pooja"]
surnames = ["Sharma", "Rao", "Mehta", "Nair", "Singh", "Patil", "Verma", "Shetty", "Kumar", "Jain"]

specializations = [
    "Criminal Law", "Civil Law", "Corporate Law",
    "Family Law", "Cyber Law", "Property Law"
]

locations = [
    "Bangalore", "Mysore", "Hubli", "Mangalore", "Udupi",
    "Belgaum", "Tumkur", "Dharwad",
    "Delhi", "Mumbai", "Chennai", "Hyderabad", "Kolkata", "Pune"
]

with open("lawyers.csv", "w", newline='', encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(["name","email","phone","specialization","experience","location"])

    for i in range(1, 121):
        name = random.choice(names) + " " + random.choice(surnames)
        email = f"lawyer{i}@gmail.com"
        phone = "9" + str(random.randint(100000000, 999999999))
        specialization = random.choice(specializations)
        experience = random.randint(2, 15)
        location = random.choice(locations)

        writer.writerow([name, email, phone, specialization, experience, location])

print("120 lawyers dataset created successfully!")