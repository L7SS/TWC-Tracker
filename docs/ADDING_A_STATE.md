# Adding a state

Federal law requires states to make claimants able, available and actively seeking work. Everything else is set by each state. **Never copy one state's rules into another.**

1. Find the state agency's official work-search form and its list of acceptable activities. Read them.
2. Add a `StateConfig` to `src/twc_tracker/states.py` and register it in `STATES`:
   - `example_activities`: quoted from the form itself.
   - `accepted_activities`: the agency's own list. Mark anything that is not on the printed list (for example, learned from agency correspondence) with a comment saying so.
   - `result_choices`: the form's own result options.
   - `reminders`: short paraphrases of the agency's own definitions and warnings.
   - `source`: the exact documents you used, and a note to verify against the claimant's own letter.
3. Do **not** hard-code a required number of searches per week. That belongs to the user's own determination letter (it is a user setting).
4. Check the code that maps tracker rows to activities (`applications.to_entries`) — it currently uses Texas activity names — and make it state-aware if your state's names differ.
5. Add tests and link the official documents in your pull request.
