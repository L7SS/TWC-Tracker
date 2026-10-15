"""One small config per state, built from that state's own official form and guidance.

Federal law requires states to make claimants able, available and actively seeking work. What counts, how many
contacts a week and which form to use are set by each state, so a state is never copied from another one.
See docs/ADDING_A_STATE.md before adding one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Texas activity names, as listed by the Texas Workforce Commission.
TX_IN_PERSON = "In-person visit, job application or interview with an employer who may reasonably have openings"
TX_APPLY_ONLINE = "Applying for a job online, on any site, to an employer who may reasonably have openings"
TX_RESEARCH = "Researching job openings on the internet"
TX_NETWORK = "Work-related networking event, job club, job fair or employment workshop"


@dataclass(frozen=True)
class StateConfig:
    code: str
    agency: str
    form: str
    example_activities: tuple[str, ...]  # quoted from the agency's own form
    result_choices: tuple[str, ...]
    keep_note: str
    accepted_activities: tuple[str, ...] = ()  # the agency's own list; "includes but is not limited to"
    source: str = ""
    reminders: tuple[str, ...] = field(default_factory=tuple)  # paraphrased from the agency's own definitions


TEXAS = StateConfig(
    code="TX",
    agency="Texas Workforce Commission",
    form="Work Search Activity Log (BN900E)",
    example_activities=(
        "Applied for job",
        "Submitted resume",
        "Attended job fair",
        "Interviewed",
        "Used Workforce Center",
        "Searched online",
    ),
    result_choices=(
        "Hired",
        "Not hiring",
        "Application filed",
        "Resume sent",
        "Interviewed",
        "Not hired",
        "No reply",
        "Other",
    ),
    keep_note="Keep this form for your records. Submit a copy to TWC only if requested.",
    source="TWC list of acceptable work search activities, form BN900E and the TWC glossary. "
    "Verify against your own determination letter and TWC's current pages: rules change.",
    reminders=(
        "True and complete: intentionally not reporting the true facts on a claim can bring civil and "
        "criminal penalties.",
        "Available for work: ready, willing and able to accept any full-time suitable work, available for "
        "interviews, and willing to accept the usual rate of pay for your qualifications and experience.",
        "Earnings include self-employment profits. If you worked but have no profits, TWC says to answer "
        "that you worked and report $0. Time spent on your own project or business may count as work: "
        "ask TWC how to report it. Hours logged here as job search must be job search, not working hours.",
        "Severance pay and wages in lieu of notice can disqualify you while you receive them. Report them.",
        "Claim weeks run Sunday to Saturday. Report earnings AND hours worked for each claim week, "
        "and report them for the week you worked, not the week you were paid.",
        "Able to work: physically and mentally able to do the work you are seeking, which exists in your area.",
        "Suitable work: TWC decides case by case from your experience, qualifications and training, local pay and "
        "conditions, risks to health or safety, commute distance and length of unemployment. Refusing a referral or "
        "suitable work can disqualify you.",
        "Normal wage: you must be willing to accept the usual rate of pay and the normal days and hours for the "
        "work you are seeking.",
        "Ineligible: TWC cannot pay any week in which you did not meet the weekly requirements, including the "
        "required number of work-search activities, or did not answer a TWC request for information.",
        "Reduced hours: working less than the customary full-time hours for your normal occupation is reported "
        "as reduced hours.",
        "Keep proof (confirmation emails, screenshots, notes with names and phone numbers with area codes) for "
        "every entry. TWC can ask for it.",
    ),
    accepted_activities=(
        "Registering on WorkInTexas.com",
        "Searching for jobs on WorkInTexas.com (including the Virtual Recruiter tool)",
        "Following up on job contacts from WorkInTexas.com or a Workforce Solutions office",
        "Registering with a private employment agency, school placement service or other job-matching system",
        TX_IN_PERSON,
        "Mailing a job application or resume as instructed by a public job notice",
        "Creating a reemployment plan",
        "Creating or uploading a resume to an online job board",
        TX_NETWORK,
        "Reemployment services at a Workforce Solutions office (labor market information, skills assessment, "
        "resume preparation workshop, interviewing workshop, targeted training)",
        "Searching for jobs on the U.S. National Labor Exchange (usnlx.com)",
        # TWC has told claimants in correspondence that applying on any site counts and that researching jobs
        # online counts. These two are not on the printed BN900E list: confirm with your own letter.
        TX_APPLY_ONLINE,
        TX_RESEARCH,
    ),
)

STATES: dict[str, StateConfig] = {"TX": TEXAS}
