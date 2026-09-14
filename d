[1mdiff --git a/autodoc/cli.py b/autodoc/cli.py[m
[1mindex 1c334d3..81169d7 100644[m
[1m--- a/autodoc/cli.py[m
[1m+++ b/autodoc/cli.py[m
[36m@@ -658,21 +658,17 @@[m [mdef finish():[m
 ### Notes[m
 {notes}[m
 """[m
[32m+[m
     # Ensure logs folder exists[m
     os.makedirs("logs", exist_ok=True)[m
 [m
[31m-    log_filename = f"logs/{today}.md"[m
[31m-[m
[31m-    with open(log_filename, "w") as f:[m
[31m-        f.write(log_content)[m
[31m-    [m
     # Create or append log file[m
     if not os.path.exists(log_filename):[m
[31m-        with open(log_filename, "w") as f:[m
[32m+[m[32m        with open(log_filename, "w", encoding="utf-8") as f:[m
             f.write(f"# Engineering Log – {date_str}\n")[m
             f.write(session_entry)[m
     else:[m
[31m-        with open(log_filename, "a") as f:[m
[32m+[m[32m        with open(log_filename, "a", encoding="utf-8") as f:[m
             f.write(session_entry)[m
 [m
     # Update CHANGELOG[m
