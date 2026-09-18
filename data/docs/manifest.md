# Dispatch Copilot — Knowledge Base Corpus Manifest

Real, publicly available emergency-dispatch reference documents collected for the
Dispatch Copilot prototype knowledge base (indexed into Moss for real-time
semantic retrieval).

- **Collected:** 2026-09-13
- **Total files:** 41 (excluding this manifest)
- **Total size:** ~30 MB
- **Formats:** 17 PDF, 23 Markdown (HTML converted to text), 1 CSV

**Provenance rule followed:** every file was fetched from the live source listed
below (direct `curl`, or via the Internet Archive where the origin host blocked
this machine). No document content was written, paraphrased, or synthesized.
Each Markdown file carries its own `Source:` URL and retrieval date in its header.

**Retrieval notes:** several `.gov` hosts (cdc.gov, phmsa.dot.gov, ems.gov,
nasemso.org, cpr.heart.org) returned 403 to direct requests from this machine.
Where that happened, the identical file was pulled from the Internet Archive
mirror of the official URL; the original URL is what is listed below, with the
mirror noted in the description and in the file header.

**Category breakdown**

| Category | Directory | Files |
|---|---|---|
| Medical emergency protocols | `medical/` | 20 |
| Hazmat / fire / environmental | `hazmat/` | 8 |
| Dispatch-specific protocol references | `dispatch-protocols/` | 6 |
| Resource / facility data | `facilities/` | 7 |

---

## 1. Medical emergency protocols — `medical/` (20 files)

| File | Source URL | Description |
|---|---|---|
| `cpr-adult-medlineplus.md` | https://medlineplus.gov/ency/article/000013.htm | Step-by-step CPR for adults and children past puberty (NIH MedlinePlus, public domain). |
| `cpr-infant-medlineplus.md` | https://medlineplus.gov/ency/article/000011.htm | Step-by-step infant CPR, including compression depth and rescue-breath technique. |
| `cpr-cardiac-arrest-aha-2025-guidelines-highlights.pdf` | https://cpr.heart.org/-/media/CPR-Files/2025-documents-for-cpr-heart-edits-posting/Resuscitation-Science/252500_Hghlghts_2025ECCGuidelines.pdf | Highlights of the 2025 AHA Guidelines for CPR and Emergency Cardiovascular Care, 24 pp (via Internet Archive mirror). |
| `choking-adult-child-medlineplus.md` | https://medlineplus.gov/ency/article/000049.htm | Choking response / Heimlich (abdominal thrusts) for a conscious adult or child over 1. |
| `choking-infant-medlineplus.md` | https://medlineplus.gov/ency/article/000048.htm | Choking response for infants under 1 — back blows and chest thrusts. |
| `stroke-medlineplus.md` | https://medlineplus.gov/ency/article/000726.htm | Stroke overview: symptoms, types, time-critical treatment window, risk factors. |
| `stroke-fast-signs-symptoms-cdc.md` | https://www.cdc.gov/stroke/signs-symptoms/index.html | CDC F.A.S.T. stroke recognition (Face/Arms/Speech/Time) (via Internet Archive mirror). |
| `severe-bleeding-hemorrhage-medlineplus.md` | https://medlineplus.gov/ency/article/000045.htm | Bleeding control first aid: direct pressure, wound types, when to call 911. |
| `stop-the-bleed-bleeding-control-guide.pdf` | https://www3.erie.gov/health/sites/www3.erie.gov.health/files/2024-07/stopthebleed.pdf | 2-page Stop the Bleed field card: 5-step bleeding control, wound packing, tourniquet use. |
| `applying-a-tourniquet-dhs-stop-the-bleed.pdf` | https://www.dhs.gov/sites/default/files/publications/STB_Applying_Tourniquet_08-06-2018_0.pdf | DHS Stop the Bleed poster — safe tourniquet application to a limb. |
| `seizures-medlineplus.md` | https://medlineplus.gov/ency/article/003200.htm | Seizure recognition, seizure first aid, and status-epilepticus red flags. |
| `anaphylaxis-medlineplus.md` | https://medlineplus.gov/ency/article/000844.htm | Anaphylaxis / severe allergic reaction: symptoms, epinephrine, emergency care. |
| `childbirth-obstetrical-emergencies-newborn-delivery-sandiego-ems.pdf` | https://www.sandiegocounty.gov/content/dam/sdc/ems/Policies_Protocols/2024/CoSD%20EMS%20S-133%202024.pdf | San Diego County EMS 2024 protocol S-133: obstetrical emergencies and newborn delivery. |
| `obstetric-emergencies-pregnancy-postpartum-ems-kansas.pdf` | https://kansaspqc.kdhe.ks.gov/wp-content/uploads/2024/04/Obstetric-Emergencies-Pregnancy-Postpartum-EMS-Practitioners.pdf | Kansas PQC field reference for EMS on pregnancy/postpartum emergencies (hemorrhage, hypertension). |
| `ems-prehospital-precipitous-delivery-statpearls.md` | https://www.ncbi.nlm.nih.gov/books/NBK525996/ | Full clinical reference on prehospital/precipitous deliveries: indications, technique, complications. |
| `drowning-non-fatal-medlineplus.md` | https://medlineplus.gov/ency/article/000046.htm | Non-fatal drowning: rescue precautions, resuscitation sequence, follow-up care. |
| `shock-medlineplus.md` | https://medlineplus.gov/ency/article/000039.htm | Shock recognition and first aid — positioning, warmth, what not to do. |
| `heart-attack-first-aid-medlineplus.md` | https://medlineplus.gov/ency/article/000063.htm | Heart attack first aid: symptom recognition, aspirin, CPR/AED escalation. |
| `hypothermia-medlineplus.md` | https://medlineplus.gov/ency/article/000038.htm | Hypothermia recognition and rewarming first aid (exposure calls). |
| `poisoning-first-aid-medlineplus.md` | https://medlineplus.gov/ency/article/007579.htm | General poisoning first aid — ingestion, inhalation, skin/eye exposure. |

## 2. Hazmat / fire / environmental — `hazmat/` (8 files)

| File | Source URL | Description |
|---|---|---|
| `emergency-response-guidebook-2024-dot-phmsa.pdf` | https://www.phmsa.dot.gov/sites/phmsa.dot.gov/files/2024-04/ERG2024-Eng-Web-a.pdf | **DOT/PHMSA 2024 Emergency Response Guidebook**, 392 pp — the canonical hazmat first-responder reference (UN/NA ID lookup, guide pages, isolation/evacuation tables). Via Internet Archive mirror. |
| `osha-hazwoper-1910-120-emergency-response.md` | https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.120 | Full text of OSHA 29 CFR 1910.120 (HAZWOPER) including paragraph (q), emergency response to hazardous substance releases. |
| `pipeline-emergency-response-guidelines-2022-gas-leak.pdf` | https://pipelineawareness.org/media/jexaytkb/2022-pipeline-emergency-response-guidelines.pdf | 52 pp pipeline/natural-gas emergency guidelines: leak recognition, evacuation distances, gas inside a building. |
| `fire-department-pipeline-response-preparedness-toolkit-nvfc.pdf` | https://www.nvfc.org/wp-content/uploads/2018/07/FD-PREPP-Toolkit.pdf | National Volunteer Fire Council toolkit on fire-department pipeline incident response and preparedness. |
| `phoenix-regional-fire-dispatch-communications-sop-205-01.pdf` | https://www.phoenix.gov/content/dam/phoenix/firesite/documents/074775.pdf | Phoenix Regional SOP M.P. 205.01 (Communications) — structure-fire alarm assignments, dispatch levels, radio procedure. |
| `carbon-monoxide-poisoning-about-cdc.md` | https://www.cdc.gov/carbon-monoxide/about/index.html | CDC guidance on carbon monoxide poisoning: symptoms, sources, immediate actions (via Internet Archive mirror). |
| `carbon-monoxide-poisoning-medlineplus.md` | https://medlineplus.gov/ency/article/002804.htm | CO poisoning clinical reference: symptoms by exposure level, home care, emergency treatment. |
| `chemical-burn-or-reaction-medlineplus.md` | https://medlineplus.gov/ency/article/000059.htm | Chemical burn / exposure first aid — decontamination, irrigation, what not to neutralize. |

## 3. Dispatch-specific protocol references — `dispatch-protocols/` (6 files)

| File | Source URL | Description |
|---|---|---|
| `national-model-ems-clinical-guidelines-nasemso-2022.pdf` | https://nasemso.org/wp-content/uploads/National-Model-EMS-Clinical-Guidelines_2022.pdf | **NASEMSO National Model EMS Clinical Guidelines v3.0 (2022), 407 pp** — the broadest single protocol reference in the corpus (cardiac arrest, airway, OB, trauma, toxicology, environmental). Via Internet Archive mirror. |
| `denver-health-paramedic-division-field-protocols-2024.pdf` | https://www.denverhealth.org/-/media/images/content-images/departments-services/paramedics/dhpd-protocols-november-14-2024.pdf | Denver Health Paramedic Division field protocols, 164 pp (Nov 2024) — a real, complete municipal EMS protocol set. |
| `emd-program-standard-s882-san-diego-county-ems.pdf` | https://www.sandiegocounty.gov/content/dam/sdc/ems/public_comment/DRAFT%20CoSD%20EMS%20S-882%20Emergency%20Medical%20Dispatch%20Programs%20CLEAN%201%203%2024.pdf | San Diego County EMS standard S-882 governing EMD programs: call triage, pre-arrival instruction requirements, QA. |
| `emergency-medical-dispatch-white-paper-virginia-vdh.pdf` | https://www.vdh.virginia.gov/content/uploads/sites/23/2016/05/EMDWhitePaper.pdf | Virginia Department of Health EMD white paper — what EMD is, medical-director-approved questioning and pre-arrival instructions. |
| `ems-pre-arrival-instructions-statpearls-ncbi.md` | https://www.ncbi.nlm.nih.gov/books/NBK470543/ | Clinical reference on EMS pre-arrival instructions — what dispatchers deliver to callers before units arrive. |
| `model-ems-protocol-naloxone-administration-nhtsa-ems-gov.pdf` | https://www.ems.gov/assets/Model-EMS-Protocol-Relating-to-Naloxone-Administration-by-EMS-Personnel.pdf | NHTSA/ems.gov model EMS protocol for suspected opioid overdose and naloxone administration. Via Internet Archive mirror. |

## 4. Resource / facility data — `facilities/` (7 files)

| File | Source URL | Description |
|---|---|---|
| `new-york-state-hospitals-facility-directory.csv` | https://health.data.ny.gov/resource/vn5v-hh5r.csv | **220 New York State hospitals** with name, street address, city, ZIP, phone, county, ownership, and latitude/longitude — the "nearest facility" demo dataset. Filtered (`fac_desc_short='HOSP'`) from the NY DOH Health Facility General Information open dataset. |
| `texas-designated-trauma-facilities-list-dshs.pdf` | https://www.dshs.texas.gov/sites/default/files/emstraumasystems/etrahosp.pdf | Texas DSHS list of all 302 designated trauma facilities by Level I–IV, with city and trauma service area. |
| `arkansas-designated-trauma-centers-list.pdf` | https://healthy.arkansas.gov/wp-content/uploads/Designated-Trauma-Centers-1.20.26.pdf | Arkansas Department of Health designated trauma centers, alphabetical by designation level. |
| `field-triage-of-injured-patients-cdc-mmwr.pdf` | https://www.cdc.gov/mmwr/pdf/rr/rr6101.pdf | CDC MMWR Recommendations & Reports: Guidelines for Field Triage of Injured Patients — the decision scheme for routing a patient to the right trauma center level. Via Internet Archive mirror. |
| `trauma-center-designation-levels-statpearls.md` | https://www.ncbi.nlm.nih.gov/books/NBK560553/ | What Level I–V trauma center designations mean, and designation vs. verification. |
| `poison-control-center-emergency-number-medlineplus.md` | https://medlineplus.gov/ency/article/002724.htm | Poison Control Center reference — the national 1-800-222-1222 hotline and what information to have ready. |
| `poison-control-help-hrsa-poisonhelp.md` | https://www.poisonhelp.org/help | America's Poison Centers / HRSA Poison Help landing page — hotline access and call-911-instead criteria. Short page; kept as the hotline's own primary reference. |

---

## Sources attempted but not included

| Source | Reason skipped |
|---|---|
| NAEMD / Priority Dispatch **MPDS** card sets (ProQA) | Proprietary and license-gated — no public full protocol text exists. Publicly available *governance* documents describing EMD programs were used instead (San Diego County S-882, Virginia VDH white paper). |
| NFPA 1221 / 1710 (alarm processing and fire response deployment standards) | NFPA free-access reading requires registration and forbids download; excluded rather than fabricated. A real municipal equivalent (Phoenix Regional SOP 205.01) was used instead. |
| Full text of the 2025 AHA CPR Guidelines in *Circulation* (ahajournals.org) | Host returns 403 / not archived. The AHA's own free **Guidelines Highlights** PDF is included instead. |
| ACS "Stop the Bleed" v3.0 Instructor Guide PDF | Downloaded successfully but is an image-only PDF with zero extractable text — useless for text retrieval, so it was discarded in favour of the text-bearing Stop the Bleed field card. |
| CMS Hospital General Information and HIFLD Open Hospitals national datasets | Both hosts blocked automated access (403 / dead service endpoints). The NY State open hospital dataset was used as the representative facility dataset instead. |
| FCC Master PSAP Registry | fcc.gov returned 403 to all requests from this machine. |

## Regenerating / verifying

Every Markdown file records its own source URL and retrieval date in its header.
PDF text extraction was verified for all 17 PDFs (`pdftotext`); all contain a
real text layer and are safe to chunk and index directly.
