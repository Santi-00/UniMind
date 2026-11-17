# Manual test checklist

Run this on your own machine after installing. Tick each item. If something fails, open an issue with the item number and the message you saw.
Use a **short PDF with selectable text** (not a scan) for the first run.

## A. Startup
| # | Step | Expected |
|---|---|---|
| A1 | Run `start_unimind.bat` / `start_unimind.sh` | Two windows/processes start; browser opens http://localhost:3000 |
| A2 | First run | A welcome box asks for your name; the dashboard greets you by name |
| A3 | Open http://127.0.0.1:8000/docs | API documentation loads |

## B. Ollama
| # | Step | Expected |
|---|---|---|
| B1 | Settings → status | Green dot "Ollama è attivo"; installed models are listed |
| B2 | Choose chat + embedding model → Save → Test connection | The model answers |
| B3 | Select a chat model as *embedding* and index (negative test) | A clear error (not a crash) |

## C. Subjects, timetable
| # | Step | Expected |
|---|---|---|
| C1 | Create, edit, delete a subject | Works; deleting asks for confirmation |
| C2 | Add / edit / duplicate / delete a timetable event | Works; end time before start time is rejected |
| C3 | Event starting in N minutes with reminder N | Browser notification appears (if allowed) |

## D. Documents and RAG
| # | Step | Expected |
|---|---|---|
| D1 | Upload a PDF, a PPTX, a DOCX, a TXT | Status goes caricato → analizzato |
| D2 | Upload an unsupported file (e.g. `.exe`) | Rejected with a message |
| D3 | Preview a document | Text with page/slide numbers |
| D4 | Search by a word inside a document | The document is found |
| D5 | Press **Index all** | Counter reaches N/N, no error |
| D6 | http://127.0.0.1:8000/api/rag/diagnostics | Every check is `ok: true` |

## E. Study in sequence and lessons
| # | Step | Expected |
|---|---|---|
| E1 | Study in sequence → document → Recognize chapters | A list of chapters with page ranges |
| E2 | Generate one lesson | Lesson with the 10 sections; "Approfondimento AI" paragraphs highlighted |
| E3 | Generate all missing lessons | Progress counter advances; finished lessons can be read meanwhile |
| E4 | Mark as studied, "Next lesson" | Progress bar updates |
| E5 | Lessons page: edit, save notes, regenerate | Notes survive regeneration |
| E6 | Math content | Formulas are rendered (not raw `$...$`) |

## F. Tutor
| # | Step | Expected |
|---|---|---|
| F1 | Ask about your document | Streaming answer with "Fonti" (file + page) |
| F2 | Ask something not in your documents | The tutor says the documents don't contain it |
| F3 | "Non ho capito" | A simpler explanation from the basics |
| F4 | Interrogation mode | One question at a time, evaluates and corrects |

## G. Tests, progress, plan
| # | Step | Expected |
|---|---|---|
| G1 | Generate a test (mixed types), submit | Score %, level, grade /30, topics to review |
| G2 | Open-ended answers | Graded with feedback; equivalent wording is not penalized |
| G3 | Progress page | Preparation updates after the test |
| G4 | Subject with exam date → Create plan | Day-by-day plan only on valid dates; "Riorganizza" regenerates |

## H. Backup and data safety
| # | Step | Expected |
|---|---|---|
| H1 | Settings → Create backup now | A zip appears in the list and in `backups/` |
| H2 | Delete a subject, then restore that backup | Subject, lessons and files are back; a safety backup is created first |
| H3 | Restore a random zip | Rejected: "Non è un backup di UniMind" |
| H4 | Export data | `unimind_export.zip` with `data.json` and lessons `.md` |
| H5 | Restart the app | All data is still there |

## I. Robustness and privacy
| # | Step | Expected |
|---|---|---|
| I1 | Stop Ollama, use tutor/lessons | A clear error; the rest of the app keeps working |
| I2 | Disconnect from the internet (after setup) | Everything still works |
| I3 | Check network activity (optional) | Only `localhost` connections |
