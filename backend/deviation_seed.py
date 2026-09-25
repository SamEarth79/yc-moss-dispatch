"""
Synthetic dispatcher deviations (choking + cardiac arrest) used to seed deviation-index.

Each record references a real chunk id from protocol_chunks.py. All metadata values are
strings, per the Moss metadata contract.
"""

import json


def _summary(what_happened: str, patient: str) -> str:
    return json.dumps({"whatHappened": what_happened, "patient": patient})


DEVIATION_SEEDS = [
    {
        "id": "dev-seed-1",
        "text": (
            "Adult is choking, cannot speak, gasping and still conscious.\n"
            "Dispatcher told the caller to give water instead of starting back blows and abdominal thrusts."
        ),
        "metadata": {
            "type": "deviation",
            "callerTranscript": "my husband is choking on steak he cant talk or breathe he is gasping",
            "callerSummary": _summary("Adult choking on food, cannot speak", "adult male, conscious"),
            "protocolChunkId": "choking-adult-2-severe",
            "protocolChunkText": "If the person cannot speak or is having a hard time breathing, perform cycles of 5 back blows and 5 abdominal thrusts.",
            "dispatcherTranscript": "Try giving him a glass of water to wash it down.",
            "deviationSummary": "Advised water for a severe choking victim instead of back blows and abdominal thrusts.",
            "reason": "Caller sounded calm",
            "timestamp": "2026-08-14T15:02:11Z",
            "seed": "true",
        },
    },
    {
        "id": "dev-seed-2",
        "text": (
            "Adult choked, collapsed and is unresponsive with no breathing.\n"
            "Dispatcher skipped the responsiveness check and had the caller start rescue breaths first."
        ),
        "metadata": {
            "type": "deviation",
            "callerTranscript": "he was choking and now he collapsed he is not moving and not breathing",
            "callerSummary": _summary("Adult collapsed after choking, not breathing", "adult male, unconscious"),
            "protocolChunkId": "cpr-adult-1-check-responsiveness",
            "protocolChunkText": "Check for responsiveness. Shake or tap the person gently and shout, Are you OK?",
            "dispatcherTranscript": "Tilt his head back and give him two breaths right away.",
            "deviationSummary": "Skipped the responsiveness check and directed rescue breaths before compressions.",
            "reason": "",
            "timestamp": "2026-08-21T09:37:45Z",
            "seed": "true",
        },
    },
    {
        "id": "dev-seed-3",
        "text": (
            "Adult in cardiac arrest, caller ready to start chest compressions.\n"
            "Dispatcher gave the wrong compression depth and rate."
        ),
        "metadata": {
            "type": "deviation",
            "callerTranscript": "my mom is not breathing and has no pulse i think her heart stopped what do i do",
            "callerSummary": _summary("Adult cardiac arrest, no pulse", "adult female, unconscious"),
            "protocolChunkId": "cpr-adult-4-compressions",
            "protocolChunkText": "Give 30 compressions, pressing down about 2 inches, at a rate of 100 to 120 per minute.",
            "dispatcherTranscript": "Push gently on her chest, about one inch, nice and slow.",
            "deviationSummary": "Instructed shallow, slow compressions instead of 2 inches deep at 100 to 120 per minute.",
            "reason": "Worried about hurting the patient",
            "timestamp": "2026-09-02T18:20:03Z",
            "seed": "true",
        },
    },
]
