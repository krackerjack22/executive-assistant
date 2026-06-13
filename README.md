# Executive Assistant Skill

The `executive-assistant` is a master skill designed for compatibility as a Claude skill. It acts as a task delegator to handle personal, household, and calendar tasks using its specialized child skills.

## Child Skills

The master skill utilizes specialized sub-skills to handle distinct tasks:

1. **`summer-camp-scheduler`**: Search for and sign up for kids' summer camps.
2. **`campsite-hunter`**: Search for and sign up for recreational camping campsites.
3. **`Add2Calendar`**: Extract calendar events from input texts, PDFs, or images and format them for Google Calendar integration.

## Usage

When you invoke the Executive Assistant, provide it with your prompt (e.g. asking to schedule a summer camp, check campsite availability, or add a flyer to your calendar). The master skill will evaluate your request and delegate it to the appropriate child skill.

## Asset Storage

For privacy and security, personal assets (like profiles) are not stored in this repository. They are maintained securely in cloud storage. The master skill knows how to reference those secure paths during execution.
