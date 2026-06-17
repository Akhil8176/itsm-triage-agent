from openai import OpenAI

import os
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
def ai_triage(title, description):
    prompt = f"""You are an expert ITSM triage agent. Analyze this IT incident and respond ONLY in this exact format:

CATEGORY: [one of: Infrastructure, Access Management, Network, Collaboration Tools, Application Support, General IT]
PRIORITY: [one of: P1 - Critical, P2 - High, P3 - Medium, P4 - Low]
SLA: [one of: 1 hour, 4 hours, 8 hours, 24 hours]
ASSIGNMENT GROUP: [one of: Infrastructure Team, Security & IAM Team, Network Operations Team, End User Computing Team, Application Support Team, Service Desk]
REASON: [one sentence explaining why you chose this priority]

Incident Title: {title}
Incident Description: {description}"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300
    )

    return response.choices[0].message.content

def run_triage():
    print("\n========== AI-Powered ITSM Incident Triage Agent ==========")
    title = input("Enter incident title: ")
    description = input("Enter incident description: ")

    print("\nAnalyzing incident with AI...\n")
    result = ai_triage(title, description)

    print("--- AI Triage Result ---")
    print(result)
    print("============================================================\n")

if __name__ == "__main__":
    run_triage()