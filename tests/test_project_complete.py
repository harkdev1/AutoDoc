import tempfile
import unittest
from pathlib import Path
import subprocess
from unittest.mock import patch

from autodoc import public_cli
from autodoc.cli import build_gallery_index_entry, build_project_completion_markdown, build_project_showcase, collect_log_linked_screenshots, copy_log_linked_screenshots, extract_log_session_summary, generate_assistant_plan, list_log_files, refresh_project_completion_documents, refresh_project_status_file, refresh_readme_after_session, replace_managed_gallery_block, slugify_project_name, update_project_evidence_index, update_project_readme, update_roadmap_gallery, write_project_completion_documents


class ProjectCompletionTests(unittest.TestCase):
    def test_build_project_completion_markdown_includes_story_status_and_lessons(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "logs").mkdir()
            (root / "screenshots").mkdir()

            log_file = root / "logs" / "2026-10-10.md"
            log_file.write_text(
                "# Engineering Log – 2026-10-10\n\n"
                "## Screenshot – Dashboard build\n"
                "![Dashboard build](../screenshots/2026-10-10_120000_dashboard-build.png)\n\n"
                "### Summary\nBuild automation for launch.\n\n"
                "### Lessons Learned\nKeep documentation close to delivery.\n",
                encoding="utf-8",
            )

            screenshot = root / "screenshots" / "2026-10-10_120000_dashboard-build.png"
            screenshot.write_bytes(b"fakepng")

            readme = root / "README.md"
            readme.write_text("# Demo Project\n\nStatus: In progress\n", encoding="utf-8")

            result = build_project_completion_markdown(
                project_root=root,
                project_name="Demo Project",
                status="Complete",
                narrative="We built the delivery flow and documented the launch path.",
                lessons=["Keep docs close to delivery.", "Use proof screenshots for stakeholder updates."],
                next_steps=["Ship the beta release.", "Set up long-term metrics tracking."],
            )

            self.assertIn("Demo Project", result)
            self.assertIn("Status: Complete", result)
            self.assertIn("Lessons learned", result)
            self.assertIn("Dashboard build", result)
            self.assertIn("Keep docs close to delivery", result)

    def test_list_log_files_returns_sorted_markdown_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs_dir = root / "logs"
            logs_dir.mkdir()
            (logs_dir / "2026-10-12.md").write_text("older", encoding="utf-8")
            (logs_dir / "2026-10-11.md").write_text("newer", encoding="utf-8")
            (logs_dir / "notes.txt").write_text("ignore", encoding="utf-8")

            files = list_log_files(root)
            self.assertEqual([path.name for path in files], ["2026-10-12.md", "2026-10-11.md"])

    def test_generate_assistant_plan_uses_project_context_and_includes_next_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "logs").mkdir()
            (root / "screenshots").mkdir()
            (root / "README.md").write_text("# Demo Project\n\nThis project is in progress.\n", encoding="utf-8")
            (root / "logs" / "2026-10-10.md").write_text("### Summary\nWe built a working prototype.\n", encoding="utf-8")
            with patch("autodoc.cli.get_api_key", return_value="test-key"), patch("autodoc.cli.genai.Client") as client_factory:
                client = client_factory.return_value
                client.chats.create.return_value.send_message.return_value.text = (
                    "# Demo Project\n\n## Current status\nA working prototype is documented.\n\n"
                    "## Next steps\nValidate the prototype with a small test."
                )
                plan = generate_assistant_plan(project_root=root, user_question="What should I do next?", project_name="Demo Project")
            self.assertIn("Demo Project", plan)
            self.assertIn("Next steps", plan)
            self.assertIn("prototype", plan.lower())

    def test_refresh_readme_after_session_updates_status_and_latest_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            readme = root / "README.md"
            readme.write_text("# Original Project\n\nOld content stays below.\n", encoding="utf-8")

            refreshed = refresh_readme_after_session(
                project_root=root,
                project_name="Original Project",
                session_summary="Finished the API integration and documented the deployment notes.",
                status="In progress",
            )

            self.assertIn("## Status: In progress", refreshed)
            self.assertIn("Latest session", refreshed)
            self.assertIn("Finished the API integration", refreshed)
            self.assertIn("Old content stays below", refreshed)

    def test_refresh_project_status_file_updates_session_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            status_path = root / "project-status.md"
            status_path.write_text("# Project Status\n\nExisting project history stays below.\n", encoding="utf-8")

            refreshed = refresh_project_status_file(
                project_root=root,
                project_name="Original Project",
                session_summary="Finished the API integration and documented the deployment notes.",
                status="In progress",
                date_str="2026-10-10",
                notes="Need the release checklist before shutdown.",
                session_details="**Goal:** Validate the API integration.\n\n**Duration:** 45 minutes.",
            )

            self.assertIn("## Status: In progress", refreshed)
            self.assertIn("## Session summary", refreshed)
            self.assertIn("Finished the API integration", refreshed)
            self.assertIn("Existing project history stays below", refreshed)
            self.assertIn("2026-10-10", refreshed)
            self.assertIn("**Goal:** Validate the API integration.", refreshed)
            self.assertIn("**Duration:** 45 minutes.", refreshed)

    def test_refresh_project_status_file_keeps_prior_sessions_and_updates_current_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            first = refresh_project_status_file(
                project_root=root,
                project_name="Original Project",
                session_summary="Configured the initial workstation policy.",
                status="In progress",
                date_str="2026-10-09",
            )
            refreshed = refresh_project_status_file(
                project_root=root,
                project_name="Original Project",
                session_summary="Validated the PowerShell diagnostics script.",
                status="In progress",
                date_str="2026-10-10",
            )

            self.assertIn("Configured the initial workstation policy.", refreshed)
            self.assertIn("Validated the PowerShell diagnostics script.", refreshed)
            self.assertIn("2026-10-09", refreshed)
            self.assertIn("2026-10-10", refreshed)
            self.assertIn("Current status: In progress", refreshed)

    def test_refresh_project_status_file_migrates_legacy_status_heading(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            status_path = root / "project-status.md"
            status_path.write_text(
                "# Original Project Status\n\n"
                "## Status: In progress\n\n"
                "## Latest session\nOld generic placeholder.\n\n"
                "## Notes\nKeep the project journal.\n\n---\n",
                encoding="utf-8",
            )

            refreshed = refresh_project_status_file(
                project_root=root,
                project_name="Original Project",
                session_summary="Recorded the latest project work.",
                status="In progress",
                date_str="2026-10-10",
            )

            self.assertEqual(refreshed.count("## Current status: In progress"), 1)
            self.assertNotIn("\n## Status: In progress\n", refreshed)
            self.assertNotIn("Old generic placeholder", refreshed)
            self.assertIn("Keep the project journal.", refreshed)

    def test_project_readme_keeps_latest_session_details_with_project_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            readme_path = root / "README.md"
            readme_path.write_text(
                "# Demo Project\n\n"
                "> **Project status:** See [project-status.md](project-status.md).\n\n"
                "## About\nExisting project details stay below the generated summary.\n",
                encoding="utf-8",
            )
            session_details = "**Goal:** Validate the telemetry pipeline.\n\n**Duration:** 45 minutes."

            refresh_project_completion_documents(
                project_root=root,
                project_name="Demo Project",
                status="In progress",
                narrative="The project is validating its telemetry pipeline.",
                latest_session=session_details,
            )

            readme_text = readme_path.read_text(encoding="utf-8")
            self.assertIn("## Status: In progress", readme_text)
            self.assertIn("The project is validating its telemetry pipeline.", readme_text)
            self.assertIn("## Latest session", readme_text)
            self.assertIn("**Goal:** Validate the telemetry pipeline.", readme_text)
            self.assertIn("**Duration:** 45 minutes.", readme_text)
            self.assertIn("[project-status.md](project-status.md)", readme_text)
            self.assertIn("Existing project details stay below the generated summary.", readme_text)

            update_project_readme(
                project_root=root,
                project_name="Demo Project",
                narrative="The project is complete after telemetry validation.",
                status="Complete",
            )
            completed_readme = readme_path.read_text(encoding="utf-8")
            self.assertIn("## Status: Complete", completed_readme)
            self.assertIn("**Goal:** Validate the telemetry pipeline.", completed_readme)
            self.assertEqual(completed_readme.count("## Latest session"), 1)

    def test_public_finish_documentation_refresh_updates_readme_and_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Public Demo\n\nProject details.\n", encoding="utf-8")
            public_cli.update_project_documentation(
                project_root=root,
                project_name="Public Demo",
                date_str="2026-10-10",
                session_summary="### Work completed\nBuilt the account diagnostics script.",
                session_details="**Goal:** Validate account diagnostics.\n\n**Duration:** 30 minutes.",
                latest_session="**Goal:** Validate account diagnostics.\n\n**Duration:** 30 minutes.",
                notes="The script ran successfully.",
                where_left_off="Test the script on another workstation.",
            )

            readme_text = (root / "README.md").read_text(encoding="utf-8")
            status_text = (root / "project-status.md").read_text(encoding="utf-8")
            self.assertIn("## Latest session", readme_text)
            self.assertIn("**Goal:** Validate account diagnostics.", readme_text)
            self.assertIn("## Current status: In progress", status_text)
            self.assertIn("Built the account diagnostics script.", status_text)
            self.assertIn("Test the script on another workstation.", status_text)

    def test_collect_log_linked_screenshots_uses_logs_and_excludes_private_captures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs_dir = root / "logs"
            screenshots_dir = root / "screenshots"
            logs_dir.mkdir()
            screenshots_dir.mkdir()
            (screenshots_dir / "dns-check.png").write_bytes(b"dns image")
            (screenshots_dir / "northstar-dns-forward-lookup-zone.png").write_bytes(b"private DNS records")
            (screenshots_dir / "activity_2026-10-10.jpg").write_bytes(b"private activity")
            (screenshots_dir / "not-linked.png").write_bytes(b"not in logs")
            log = logs_dir / "2026-10-10.md"
            log.write_text(
                "## Screenshot – DNS check\n![Final DNS health check](../screenshots/dns-check.png)\n"
                "![DNS zone](../screenshots/northstar-dns-forward-lookup-zone.png)\n"
                "![Activity](../screenshots/activity_2026-10-10.jpg)\n",
                encoding="utf-8",
            )

            found = collect_log_linked_screenshots(root)

            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]["caption"], "Final DNS health check")
            self.assertEqual(found[0]["source"], screenshots_dir / "dns-check.png")
            self.assertEqual(found[0]["log"], log)

    def test_copy_log_linked_screenshots_verifies_transferred_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_screenshots = root / "source" / "screenshots"
            source_screenshots.mkdir(parents=True)
            source = source_screenshots / "dns-check.png"
            source.write_bytes(b"verified screenshot bytes")
            log = root / "source" / "logs" / "2026-10-10.md"
            log.parent.mkdir()
            log.write_text("log", encoding="utf-8")
            gallery = root / "roadmap" / "projects" / "demo-project"

            copied = copy_log_linked_screenshots(
                root / "source",
                gallery,
                [{"source": source, "caption": "DNS check", "log": log}],
            )

            target = gallery / "screenshots" / source.name
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertEqual(copied[0]["gallery_path"], target)

    def test_gallery_markers_update_one_card_and_preserve_other_content(self):
        text = (
            "# Gallery\n\n## Project gallery\n\n"
            "<!-- autodoc:project:other:start -->\nOther card\n<!-- autodoc:project:other:end -->\n"
        )
        entry = build_gallery_index_entry(
            "Demo Project",
            "demo-project",
            "Complete",
            "Built a verified local delivery workflow.",
            [{"caption": "DNS check", "gallery_path": Path("/tmp/dns.png")}],
            "https://github.com/example/demo",
        )
        marker_start = "<!-- autodoc:project:demo-project:start -->"
        marker_end = "<!-- autodoc:project:demo-project:end -->"

        updated = replace_managed_gallery_block(text, marker_start, marker_end, entry, "## Project gallery")
        updated_again = replace_managed_gallery_block(updated, marker_start, marker_end, entry, "## Project gallery")

        self.assertEqual(updated_again.count(marker_start), 1)
        self.assertIn("Other card", updated_again)
        self.assertIn("Source repository", updated_again)
        self.assertIn("projects/demo-project/README.md", updated_again)

    def test_project_showcase_links_source_repo_logs_and_transferred_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs = root / "logs"
            logs.mkdir()
            (logs / "2026-10-10.md").write_text(
                "## Session – 12:00 to 12:30\nSummary:\nVerified the DNS health checks.\n",
                encoding="utf-8",
            )
            image = Path(tmp) / "roadmap" / "screenshots" / "dns-check.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"image")

            showcase = build_project_showcase(
                root,
                "Demo Project",
                "Complete",
                "Built a small-business lab and verified DNS health.",
                [{"caption": "Final DNS check", "gallery_path": image, "log": logs / "2026-10-10.md"}],
                "https://github.com/example/demo",
                "main",
            )

            self.assertIn("![Final DNS check](screenshots/dns-check.png)", showcase)
            self.assertIn("https://github.com/example/demo/blob/main/logs/2026-10-10.md", showcase)
            self.assertIn("What I built", showcase)
            self.assertIn("Complete", showcase)

    def test_gallery_session_summary_displays_actual_log_summary_and_outcome(self):
        body = (
            "### Goal Achieved\n❌ No\n\n"
            "Summary:\nThe process-creation event was not reliably visible under the current audit policy.\n\n"
            "Tasks Completed:\nTested controlled activity.\n"
        )

        summary = extract_log_session_summary(body)

        self.assertIn("Recorded outcome: ❌ No.", summary)
        self.assertIn("process-creation event was not reliably visible", summary)
        self.assertNotIn("Tasks Completed", summary)

    def test_evidence_index_embeds_transferred_images_and_links_source_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "CyberOps-Sandbox"
            source_log = source / "logs" / "2026-10-08.md"
            source_log.parent.mkdir(parents=True)
            source_log.write_text("## Screenshot – DNS\n", encoding="utf-8")
            gallery = root / "roadmap" / "projects" / "cyberops-sandbox"
            gallery.mkdir(parents=True)
            image = gallery / "screenshots" / "dns-check.png"
            image.parent.mkdir()
            image.write_bytes(b"verified image")
            (gallery / "evidence-index.md").write_text(
                "# CyberOps Evidence Index\n\n## Transferred screenshots\n",
                encoding="utf-8",
            )
            screenshots = [{"caption": "Final DNS check", "source": source / "screenshots" / "dns-check.png", "log": source_log, "gallery_path": image}]
            screenshots[0]["source"].parent.mkdir(parents=True)
            screenshots[0]["source"].write_bytes(b"verified image")

            index_path = update_project_evidence_index(
                gallery,
                source,
                "CyberOps Sandbox",
                screenshots,
                "https://github.com/harkdev1/CyberOps-Sandbox",
                "main",
            )

            index_text = index_path.read_text(encoding="utf-8")
            self.assertIn("![Final DNS check](screenshots/dns-check.png)", index_text)
            self.assertIn("https://github.com/harkdev1/CyberOps-Sandbox/blob/main/logs/2026-10-08.md", index_text)
            self.assertEqual(index_text.count("<!-- autodoc:evidence-gallery:start -->"), 1)

    def test_update_roadmap_gallery_copies_log_screenshots_and_links_live_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            roadmap_root = root / "roadmap"
            source_root = root / "CyberOps-Sandbox"
            (roadmap_root / "projects" / "cyberops-sandbox").mkdir(parents=True)
            (source_root / "logs").mkdir(parents=True)
            (source_root / "screenshots").mkdir()
            (roadmap_root / "README.md").write_text("# Roadmap\n\n## Gallery\n", encoding="utf-8")
            (roadmap_root / "projects" / "cyberops-sandbox" / "README.md").write_text(
                "# CyberOps Sandbox\n\n## Showcase\n", encoding="utf-8"
            )
            (roadmap_root / "projects" / "cyberops-sandbox" / "evidence-index.md").write_text(
                "# CyberOps Evidence Index\n\n## Transferred screenshots\n", encoding="utf-8"
            )
            screenshot = source_root / "screenshots" / "telemetry-gap.png"
            screenshot.write_bytes(b"verified image payload")
            log = source_root / "logs" / "2026-10-08.md"
            log.write_text(
                "## Screenshot - Visibility gap\n![Telemetry Visibility Gap](../screenshots/telemetry-gap.png)\n\n"
                "## Session – 05:19 to 05:30\n### Goal Achieved\n✅ Yes\n\n"
                "Summary:\nThe process event was not reliably visible in the current audit configuration.\n\n"
                "Tasks Completed:\nTested process telemetry.\n",
                encoding="utf-8",
            )

            for repo in (roadmap_root, source_root):
                subprocess.run(["git", "init", "--initial-branch=main"], cwd=repo, capture_output=True, check=True)
                subprocess.run(["git", "config", "user.name", "AutoDoc Tests"], cwd=repo, check=True)
                subprocess.run(["git", "config", "user.email", "autodoc-tests@example.invalid"], cwd=repo, check=True)
                subprocess.run(["git", "add", "."], cwd=repo, check=True)
                subprocess.run(["git", "commit", "-m", "Initial test fixture"], cwd=repo, capture_output=True, check=True)
            subprocess.run(
                ["git", "remote", "add", "origin", "https://github.com/example/CyberOps-Sandbox.git"],
                cwd=source_root,
                check=True,
            )

            project_folder, copied = update_roadmap_gallery(
                roadmap_root=roadmap_root,
                project_root=source_root,
                project_name="CyberOps Sandbox",
                status="In progress",
                narrative="The homelab is validating real Windows security telemetry.",
                approved_screenshots=collect_log_linked_screenshots(source_root),
            )

            page = (project_folder / "README.md").read_text(encoding="utf-8")
            index = (project_folder / "evidence-index.md").read_text(encoding="utf-8")
            root_index = (roadmap_root / "README.md").read_text(encoding="utf-8")
            target = project_folder / "screenshots" / screenshot.name
            self.assertEqual(target.read_bytes(), screenshot.read_bytes())
            self.assertIn("Main Homelab", page)
            self.assertIn("The process event was not reliably visible", page)
            self.assertIn("https://github.com/example/CyberOps-Sandbox/blob/main/logs/2026-10-08.md", page)
            self.assertIn("![Telemetry Visibility Gap](screenshots/telemetry-gap.png)", index)
            self.assertIn("projects/cyberops-sandbox/screenshots/telemetry-gap.png", root_index)

    def test_build_project_completion_markdown_prefers_significant_screenshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "screenshots").mkdir()
            (root / "logs").mkdir()
            (root / "docs").mkdir()

            newest = root / "screenshots" / "2026-10-10_100000_temp-progress.png"
            newest.write_bytes(b"fakepng")
            important = root / "screenshots" / "2026-10-08_080000_telemetry-visibility-gap.png"
            important.write_bytes(b"fakepng")

            result = build_project_completion_markdown(
                project_root=root,
                project_name="Demo Project",
                status="In progress",
                narrative="We are validating telemetry visibility before the next phase.",
                lessons=["Use the strongest proof to explain progress."],
                next_steps=["Fix the telemetry issue."],
                output_path=root / "docs" / "project-complete-short.md",
            )

            self.assertIn("telemetry visibility gap", result.lower())
            self.assertIn("This screenshot shows the telemetry", result)
            self.assertLess(result.lower().find("telemetry visibility gap"), result.lower().find("temp progress"))

    def test_write_project_completion_documents_overwrites_short_and_appends_long(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            short_path = root / "docs" / "project-complete-short.md"
            long_path = root / "docs" / "project-complete-long.md"
            short_path.write_text("old short\n", encoding="utf-8")
            long_path.write_text("old long\n", encoding="utf-8")

            write_project_completion_documents(
                project_root=root,
                project_name="Demo Project",
                status="In progress",
                narrative="Current sprint focus is securing the telemetry pipeline.",
                lessons=["Capture evidence as work happens."],
                next_steps=["Finish the telemetry validation pass."],
                short_path=short_path,
                long_path=long_path,
            )

            self.assertIn("Current sprint focus is securing the telemetry pipeline", short_path.read_text(encoding="utf-8"))
            self.assertNotIn("old short", short_path.read_text(encoding="utf-8"))
            long_text = long_path.read_text(encoding="utf-8")
            self.assertIn("Current sprint focus is securing the telemetry pipeline", long_text)
            self.assertIn("old long", long_text)

    def test_refresh_project_completion_documents_updates_current_snapshot_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            docs.mkdir()
            short_path = docs / "project-complete-short.md"
            long_path = docs / "project-complete-long.md"
            short_path.write_text("# Old snapshot\n", encoding="utf-8")
            long_path.write_text("# Earlier milestone\n\nPrior work remains documented.\n", encoding="utf-8")
            (root / "README.md").write_text("# Demo Project\n\nExisting details.\n", encoding="utf-8")

            refresh_project_completion_documents(
                project_root=root,
                project_name="Demo Project",
                status="In progress",
                narrative="The current milestone validates telemetry visibility.",
            )

            short_text = short_path.read_text(encoding="utf-8")
            long_text = long_path.read_text(encoding="utf-8")
            readme_text = (root / "README.md").read_text(encoding="utf-8")
            self.assertIn("Status: In progress", short_text)
            self.assertIn("The current milestone validates telemetry visibility.", short_text)
            self.assertNotIn("Old snapshot", short_text)
            self.assertIn("Earlier milestone", long_text)
            self.assertIn("The current milestone validates telemetry visibility.", long_text)
            self.assertIn("## Status: In progress", readme_text)

    def test_build_project_completion_markdown_long_form_includes_timeline_and_trials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "logs").mkdir()
            (root / "screenshots").mkdir()

            log_file = root / "logs" / "2026-10-10.md"
            log_file.write_text(
                "# Engineering Log – 2026-10-10\n\n"
                "## Session – 09:00 to 09:45\n"
                "### Goal\nBuild the dashboard prototype\n\n"
                "### Working Story\nWe got the first version working.\n\n"
                "### Friction and AI Gaps\nThe first pass missed the layout edge case.\n\n"
                "### What the AI Missed\nIt did not include mobile spacing.\n\n"
                "### Duration\n45 minutes (Planned: 60 minutes)\n\n"
                "## Screenshot – Dashboard prototype\n"
                "![Dashboard prototype](../screenshots/dashboard-prototype.png)\n",
                encoding="utf-8",
            )

            screenshot = root / "screenshots" / "dashboard-prototype.png"
            screenshot.write_bytes(b"fakepng")

            result = build_project_completion_markdown(
                project_root=root,
                project_name="Example Feature Project",
                status="Example complete",
                narrative="We built the example feature and documented the journey.",
                lessons=["Document decisions as they happen."],
                next_steps=["Keep iterating."],
                long_form=True,
            )

            self.assertIn("Project timeline", result)
            self.assertIn("Trials and tribulations", result)
            self.assertIn("09:00 to 09:45", result)
            self.assertIn("mobile spacing", result)


if __name__ == "__main__":
    unittest.main()
