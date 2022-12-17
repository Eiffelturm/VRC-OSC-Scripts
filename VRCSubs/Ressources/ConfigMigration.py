import ruamel.yaml
import tkinter as tk
from tkinter import filedialog, messagebox

root = tk.Tk()
root.iconbitmap("Icon.ico")
root.withdraw()

old_config = filedialog.askopenfilename(filetypes=[('VRChat YML Config Files', '.yml')], title="Select old config")
if old_config == "":
    messagebox.showerror("Missing file", "You didn't select a file!")
    quit()

new_config = filedialog.askopenfilename(filetypes=[('VRChat YML Config Files', '.yml')], title="Select new config")
if new_config == "":
    messagebox.showerror("Missing file", "You didn't select a file!")
    quit()

yaml = ruamel.yaml.YAML()
yaml.default_flow_style = False

migrated = 0
removed = 0

with open(old_config, "r") as f:
    old_data = yaml.load(f)

with open(new_config, "r") as f:
    new_data: ruamel.yaml.CommentedMap = yaml.load(f)

    for value in old_data:
        try:
            if new_data[value] != old_data[value]:
                new_data[value] = old_data[value]
                print(f"Migrated {value}...\n")
                migrated += 1
            else:
                print(f"{value} didn't change...\n")
        except KeyError:
            removed += 1
            pass
            # new_data.insert(0, value, old_data[value], "Added by config migration")
            # print(f"Added {value}...")
            # print(new_data)
            # added += 1

with open(new_config, "w") as f:
    yaml.indent(offset=2)
    yaml.dump(new_data, f)

print("\nMigration complete!")
messagebox.showinfo("VRCSubs", f"Migration complete\n\nMigrated {migrated} settings\nRemoved {removed} settings from older version")