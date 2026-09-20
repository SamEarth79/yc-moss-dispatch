"""
MVP protocol index content: choking + cardiac arrest only (per Plan.md §5 scope decision).

Every chunk's text is copied verbatim from data/docs/medical/{choking,cpr}-adult-*.md —
no paraphrasing, so citations back to the source doc stay accurate.

Chunk boundaries are cut at instructional-step / severity-escalation points (not fixed-size
splitting) so the live panel can jump to a more urgent step as the caller's words escalate.
"""

PROTOCOL_CHUNKS = [
    {
        "id": "choking-adult-1-mild",
        "text": (
            'Ask the person, "Are you choking? Can you speak?" If the person is coughing '
            "forcefully and is able to speak, do not perform first aid. A strong cough can "
            "dislodge the object on its own — encourage the person to keep coughing."
        ),
        "metadata": {
            "protocolType": "choking",
            "ageGroup": "adult",
            "severityStage": "conscious-mild",
            "priority": "P3-monitor",
            "suggestedAction": "monitor-no-dispatch",
            "sourceDoc": "data/docs/medical/choking-adult-child-medlineplus.md",
            "stepOrder": "1",
            "nextChunkId": "choking-adult-2-severe",
        },
    },
    {
        "id": "choking-adult-2-severe",
        "text": (
            "If the person cannot speak or is having a hard time breathing — cannot breathe, "
            "cannot get air, gasping — act fast while they are still conscious. Perform "
            "repeated cycles of 5 back blows followed by 5 abdominal thrusts (Heimlich maneuver) "
            "until the object comes out or the person becomes unconscious. To give a back blow: "
            "stand behind the person, lean them forward, and use the heel of your hand to strike "
            "firmly between the shoulder blades. To give an abdominal thrust: stand behind the "
            "person, make a fist just above the navel, grasp it with your other hand, and give a "
            "quick, upward and inward thrust."
        ),
        "metadata": {
            "protocolType": "choking",
            "ageGroup": "adult",
            "severityStage": "conscious-severe",
            "priority": "P1-critical",
            "suggestedAction": "dispatch-EMS-ambulance",
            "sourceDoc": "data/docs/medical/choking-adult-child-medlineplus.md",
            "stepOrder": "2",
        },
    },
    {
        "id": "choking-adult-2b-pregnant-obese",
        "text": (
            "For a pregnant or obese person who cannot speak or breathe: wrap your arms around "
            "the person's chest instead of the waist. Place your fist in the middle of the "
            "breastbone between the nipples and give firm, backward chest thrusts instead of "
            "abdominal thrusts. Continue in cycles of 5."
        ),
        "metadata": {
            "protocolType": "choking",
            "ageGroup": "adult",
            "variant": "pregnant-or-obese",
            "severityStage": "conscious-severe",
            "priority": "P1-critical",
            "suggestedAction": "dispatch-EMS-ambulance",
            "sourceDoc": "data/docs/medical/choking-adult-child-medlineplus.md",
            "stepOrder": "2b",
        },
    },
    {
        "id": "cpr-adult-1-check-responsiveness",
        "text": (
            'Check for responsiveness. Shake or tap the person gently and shout, "Are you OK?" '
            "See if the person moves or makes a noise."
        ),
        "metadata": {
            "protocolType": "cardiac-arrest",
            "ageGroup": "adult",
            "severityStage": "assessing",
            "priority": "P2-assess",
            "suggestedAction": "none",
            "sourceDoc": "data/docs/medical/cpr-adult-medlineplus.md",
            "stepOrder": "1",
            "nextChunkId": "cpr-adult-3-position",
        },
    },
    {
        "id": "cpr-adult-3-position",
        "text": (
            "Carefully place the person on their back on a firm, flat surface. If a spinal "
            "injury is possible, two people should move the person together to prevent the head "
            "and neck from twisting."
        ),
        "metadata": {
            "protocolType": "cardiac-arrest",
            "ageGroup": "adult",
            "severityStage": "unresponsive",
            "priority": "P1-critical",
            "suggestedAction": "dispatch-EMS-ambulance",
            "sourceDoc": "data/docs/medical/cpr-adult-medlineplus.md",
            "stepOrder": "3",
            "nextChunkId": "cpr-adult-4-compressions",
        },
    },
    {
        "id": "cpr-adult-4-compressions",
        "text": (
            "Begin chest compressions. Place the heel of one hand in the center of the chest, "
            "between the nipples, with your other hand on top and fingers interlaced. Position "
            "your body directly over your hands with your elbows locked. Give 30 compressions, "
            "pressing down about 2 inches, fast and hard with no pausing, at a rate of 100 to 120 "
            "per minute."
        ),
        "metadata": {
            "protocolType": "cardiac-arrest",
            "ageGroup": "adult",
            "severityStage": "not-breathing-no-pulse",
            "priority": "P1-critical",
            "suggestedAction": "dispatch-EMS-ambulance",
            "sourceDoc": "data/docs/medical/cpr-adult-medlineplus.md",
            "stepOrder": "4",
            "nextChunkId": "cpr-adult-5-airway-breaths",
        },
    },
    {
        "id": "cpr-adult-5-airway-breaths",
        "text": (
            "After 30 compressions, open the airway by lifting the chin with two fingers while "
            "tilting the head back with your other hand. If the person is not breathing, cover "
            "their mouth tightly with yours, pinch the nose closed, and give 2 rescue breaths, "
            "each about a second long, watching for the chest to rise."
        ),
        "metadata": {
            "protocolType": "cardiac-arrest",
            "ageGroup": "adult",
            "severityStage": "not-breathing-no-pulse",
            "priority": "P1-critical",
            "suggestedAction": "dispatch-EMS-ambulance",
            "sourceDoc": "data/docs/medical/cpr-adult-medlineplus.md",
            "stepOrder": "5",
            "nextChunkId": "cpr-adult-6-repeat-aed",
        },
    },
    {
        "id": "cpr-adult-6-repeat-aed",
        "text": (
            "Repeat cycles of 30 chest compressions and 2 rescue breaths until the person "
            "recovers or help arrives. If an AED is available, use it as soon as possible and "
            "follow its prompts exactly. If two or more rescuers are available, switch "
            "compressors every 2 minutes to prevent fatigue. If opioid overdose is suspected and "
            "the person is not breathing, give naloxone if available without interrupting CPR."
        ),
        "metadata": {
            "protocolType": "cardiac-arrest",
            "ageGroup": "adult",
            "severityStage": "not-breathing-no-pulse",
            "priority": "P1-critical",
            "suggestedAction": "dispatch-EMS-ambulance-and-AED",
            "sourceDoc": "data/docs/medical/cpr-adult-medlineplus.md",
            "stepOrder": "6",
        },
    },
]
