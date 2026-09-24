"""Pop the next queued comic for a freed Kaggle slot.
usage: pop.py <slot>   (slot '' = blank account)
Prints one line 'CASE|ISSUE|PROFILE|PAGES' and updates queue/budgets, or prints nothing."""
import json
import sys

slot = sys.argv[1] if len(sys.argv) > 1 else ""
budgets = json.load(open("orchestrator/budgets.json"))
queue = json.load(open("orchestrator/queue.json"))
if budgets.get(slot, 0) <= 0:
    sys.stderr.write("No budget left for slot '%s'\n" % slot)
    sys.exit(0)
if not queue:
    sys.stderr.write("Queue empty\n")
    sys.exit(0)
item = queue.pop(0)
budgets[slot] = budgets.get(slot, 0) - 1
json.dump(queue, open("orchestrator/queue.json", "w"), indent=2)
json.dump(budgets, open("orchestrator/budgets.json", "w"), indent=2)
print("%s|%s|%s|%s" % (item["case"], item["issue_no"], item["profile"], item.get("target_pages", 25)))
