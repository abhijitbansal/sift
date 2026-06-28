"""Unit tests for CLI command dispatch (no network: run/dry-run excluded)."""

from datetime import datetime, timezone

from sift import cli, store


def write_cfg(tmp_path, email_block=""):
    body = (
        '[sift]\ninterest_profile = "x"\n\n'
        '[[feeds]]\nname = "F"\nurl = "https://f"\n' + email_block
    )
    path = tmp_path / "config.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_week_id_uses_iso_week():
    when = datetime(2026, 6, 28, tzinfo=timezone.utc)
    iso = when.isocalendar()

    assert cli.week_id(when) == f"{iso.year}-{iso.week:02d}"


def test_history_empty(tmp_path, capsys):
    cfg = write_cfg(tmp_path)

    rc = cli.main(["--config", str(cfg), "history"])

    assert rc == 0
    assert "No digests recorded yet" in capsys.readouterr().out


def test_history_prints_recorded_run(tmp_path, capsys):
    cfg = write_cfg(tmp_path)
    with store.connect(tmp_path / "sift.db") as conn:
        store.record_digest(
            conn, "2026-26", 5,
            model="claude-opus-4-8", input_tokens=1000, output_tokens=500, cost_usd=0.0175,
        )

    rc = cli.main(["--config", str(cfg), "history"])

    out = capsys.readouterr().out
    assert rc == 0
    assert "2026-26" in out
    assert "0.0175" in out


def test_list_prints_feeds(tmp_path, capsys):
    cfg = write_cfg(tmp_path)

    rc = cli.main(["--config", str(cfg), "list"])

    assert rc == 0
    assert "F: https://f" in capsys.readouterr().out


def test_email_command_errors_when_disabled(tmp_path, capsys):
    cfg = write_cfg(tmp_path)  # no [email] block → cfg.email is None

    rc = cli.main(["--config", str(cfg), "email", "2026-26"])

    assert rc == 1
    assert "not enabled" in capsys.readouterr().err


def test_email_command_errors_when_digest_missing(tmp_path, capsys):
    cfg = write_cfg(
        tmp_path,
        email_block=(
            '\n[email]\nenabled = true\nhost = "smtp.example.com"\n'
            'from = "a@b.com"\nto = "c@d.com"\n'
        ),
    )

    rc = cli.main(["--config", str(cfg), "email", "2026-99"])

    assert rc == 1
    assert "No digest found" in capsys.readouterr().err


def seed_content(tmp_path):
    content = tmp_path / "content"
    content.mkdir(parents=True, exist_ok=True)
    for name in ("index", "how-it-works", "features", "sources", "guide", "roadmap"):
        (content / f"{name}.md").write_text(f"# {name}", encoding="utf-8")


def test_run_dry_run_prints_prompt_without_network(tmp_path, capsys, monkeypatch):
    from sift import fetch

    cfg = write_cfg(tmp_path)
    item = fetch.Item("Title", "https://x", "F", None, "summary")
    monkeypatch.setattr(fetch, "fetch_all", lambda feeds: ([item], []))

    rc = cli.main(["--config", str(cfg), "run", "--dry-run"])

    out = capsys.readouterr().out
    assert rc == 0
    assert "[dry-run]" in out
    assert "Reader interest profile" in out


def test_run_reports_nothing_new_on_empty_fetch(tmp_path, monkeypatch):
    from sift import fetch

    cfg = write_cfg(tmp_path)
    monkeypatch.setattr(fetch, "fetch_all", lambda feeds: ([], []))

    rc = cli.main(["--config", str(cfg), "run", "--dry-run"])

    assert rc == 0


def test_run_writes_digest_and_rebuilds_site(tmp_path, monkeypatch):
    from sift import fetch, rank

    cfg = write_cfg(tmp_path)
    seed_content(tmp_path)
    monkeypatch.setattr(
        fetch, "fetch_all",
        lambda feeds: ([fetch.Item("T", "https://x", "F", None, "s")], [
            fetch.FeedResult("F", "https://f", 1, ok=True),
        ]),
    )
    good = {
        "cluster_ids": [0], "title": "Big news", "category": "tooling", "score": 8,
        "rationale": "r", "summary": "One. Two.", "needs_verification": False,
    }
    monkeypatch.setattr(
        rank, "rank_clusters",
        lambda clusters, cfg: rank.RankResult([good], "claude-opus-4-8", 100, 50),
    )

    rc = cli.main(["--config", str(cfg), "run"])

    assert rc == 0
    digest_htmls = [
        p for p in (tmp_path / "docs" / "digests").glob("*.html") if p.name != "index.html"
    ]
    assert len(digest_htmls) == 1
    assert "Big news" in digest_htmls[0].read_text(encoding="utf-8")
    with store.connect(tmp_path / "sift.db") as conn:
        history = store.digest_history(conn)
    assert history[0].item_count == 1
    assert history[0].cost_usd > 0
    assert (tmp_path / "docs" / "index.html").exists()  # site was rebuilt


def test_run_records_but_writes_nothing_when_all_filtered(tmp_path, monkeypatch):
    from sift import fetch, rank

    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(
        '[sift]\ninterest_profile = "x"\nmin_score = 5\n\n'
        '[[feeds]]\nname = "F"\nurl = "https://f"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        fetch, "fetch_all", lambda feeds: ([fetch.Item("T", "https://x", "F", None, "s")], [])
    )
    low_story = {
        "cluster_ids": [0], "title": "low", "category": "tooling", "score": 2,
        "rationale": "r", "summary": "One. Two.", "needs_verification": False,
    }
    monkeypatch.setattr(
        rank, "rank_clusters",
        lambda clusters, cfg: rank.RankResult([low_story], "claude-opus-4-8", 100, 50),
    )

    rc = cli.main(["--config", str(cfg_path), "run"])

    assert rc == 0
    # No per-week digest file was written (glob on a missing dir yields nothing).
    assert list((tmp_path / "docs" / "digests").glob("*.json")) == []
    # But the run (and its cost) was recorded so we don't re-pay to re-rank.
    with store.connect(tmp_path / "sift.db") as conn:
        history = store.digest_history(conn)
    assert len(history) == 1
    assert history[0].item_count == 0
    assert history[0].cost_usd > 0


def test_site_command_builds_docs(tmp_path, capsys):
    cfg = write_cfg(tmp_path)
    seed_content(tmp_path)

    rc = cli.main(["--config", str(cfg), "site"])

    assert rc == 0
    assert "Built" in capsys.readouterr().out
    assert (tmp_path / "docs" / "index.html").exists()


def test_maybe_rebuild_site_is_best_effort(tmp_path):
    from sift import config as config_mod

    cfg_path = write_cfg(tmp_path)
    seed_content(tmp_path)
    cfg = config_mod.load_config(cfg_path)

    cli._maybe_rebuild_site(tmp_path, tmp_path / "sift.db", cfg)

    assert (tmp_path / "docs" / "index.html").exists()


def test_maybe_rebuild_site_swallows_errors(tmp_path, monkeypatch):
    from sift import config as config_mod
    from sift import site

    cfg = config_mod.load_config(write_cfg(tmp_path))

    def boom(*args, **kwargs):
        raise RuntimeError("site build failed")

    monkeypatch.setattr(site, "build_site", boom)

    # Best-effort: must not raise even though build_site blows up.
    cli._maybe_rebuild_site(tmp_path, tmp_path / "sift.db", cfg)


def test_email_command_success(tmp_path, capsys, monkeypatch):
    cfg = write_cfg(
        tmp_path,
        email_block=(
            '\n[email]\nenabled = true\nhost = "smtp.example.com"\n'
            'from = "a@b.com"\nto = "c@d.com"\n'
        ),
    )
    out_dir = tmp_path / "docs" / "digests"
    out_dir.mkdir(parents=True)
    (out_dir / "2026-26.html").write_text("<p>digest</p>", encoding="utf-8")
    monkeypatch.setenv("SIFT_SMTP_PASSWORD", "pw")
    monkeypatch.setattr("sift.deliver._smtp_transport", lambda cfg, pw, msg: None)

    rc = cli.main(["--config", str(cfg), "email", "2026-26"])

    assert rc == 0
    assert "Emailed digest 2026-26" in capsys.readouterr().out


def write_cfg_with_bridge(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        '[sift]\ninterest_profile = "x"\n\n'
        '[x]\nbridge_url = "https://nitter.net/{handle}/rss"\n\n'
        '[[feeds]]\nname = "F"\nurl = "https://f"\n',
        encoding="utf-8",
    )
    return path


def test_add_x_errors_without_bridge(tmp_path, capsys):
    cfg = write_cfg(tmp_path)  # no [x] section

    rc = cli.main(["--config", str(cfg), "add-x", "karpathy"])

    assert rc == 1
    assert "No X bridge" in capsys.readouterr().err


def test_add_x_adds_validated_handle(tmp_path, capsys, monkeypatch):
    cfg = write_cfg_with_bridge(tmp_path)
    monkeypatch.setattr(cli, "_validate_feed", lambda url: ("X feed", None))

    rc = cli.main(["--config", str(cfg), "add-x", "@karpathy"])

    assert rc == 0
    assert "X · @karpathy" in capsys.readouterr().out
    assert "https://nitter.net/karpathy/rss" in cfg.read_text(encoding="utf-8")


def test_add_x_rejects_invalid_feed(tmp_path, capsys, monkeypatch):
    cfg = write_cfg_with_bridge(tmp_path)
    monkeypatch.setattr(cli, "_validate_feed", lambda url: (None, "did not resolve: boom"))

    rc = cli.main(["--config", str(cfg), "add-x", "karpathy"])

    assert rc == 1
    assert "did not resolve" in capsys.readouterr().err


def test_add_command_rejects_unresolvable_url(tmp_path, capsys, monkeypatch):
    import httpx

    cfg = write_cfg(tmp_path)

    def boom(*args, **kwargs):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx, "get", boom)

    rc = cli.main(["--config", str(cfg), "add", "https://nope.example.com"])

    assert rc == 1
    assert "did not resolve" in capsys.readouterr().err
