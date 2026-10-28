"""Entry speed: the app sends how long an entry took with the save; the dashboard shows the median."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import inspect, select

from app.models import EntryTiming, InputMethod
from app.services.entry_speed import RECENT_ENTRIES


def confirm_body(**fields) -> dict:
    return {"raw_text": "tanvir 90 taka baki", "type": "credit", "amount": 90,
            "new_customer": {"name": "Tanvir"}} | fields  # fmt: skip


def timings(db) -> list[EntryTiming]:
    db.expire_all()
    return list(db.scalars(select(EntryTiming).order_by(EntryTiming.id)))


def test_a_save_with_timing_keeps_only_the_numbers(client, shop, db):
    response = client.post(
        f"/shops/{shop['id']}/parse/confirm",
        json=confirm_body(timing={"duration_ms": 8400, "input": "voice"}),
    )
    assert response.status_code == 201, response.text

    [row] = timings(db)
    assert (row.shop_id, row.duration_ms, row.input_method, row.entry_count) == (
        shop["id"], 8400, InputMethod.VOICE, 1,
    )  # fmt: skip
    # Nothing else is stored: no sentence, no customer.
    columns = {c.key for c in inspect(EntryTiming).columns}
    assert columns == {"id", "shop_id", "duration_ms", "input_method", "entry_count", "created_at"}


def test_several_entries_are_one_timing(client, shop, db):
    entries = [
        confirm_body(raw_text="a 1 baki, b 2 dilo", new_customer={"name": "A"}),
        confirm_body(raw_text="a 1 baki, b 2 dilo", type="payment", new_customer={"name": "B"}),
    ]
    response = client.post(
        f"/shops/{shop['id']}/parse/confirm-many",
        json={"entries": entries, "timing": {"duration_ms": 15000, "input": "typed"}},
    )
    assert response.status_code == 201, response.text
    [row] = timings(db)
    assert (row.duration_ms, row.entry_count, row.input_method) == (15000, 2, InputMethod.TYPED)


def test_no_timing_or_an_impossible_one_saves_the_entry_but_no_timing(client, shop, db):
    url = f"/shops/{shop['id']}/parse/confirm"
    assert client.post(url, json=confirm_body()).status_code == 201
    over_an_hour = {"duration_ms": 2 * 60 * 60 * 1000, "input": "typed"}
    response = client.post(
        url, json=confirm_body(new_customer={"name": "Rina"}, timing=over_an_hour)
    )
    assert response.status_code == 201
    assert timings(db) == []


def test_a_failed_save_keeps_no_timing(client, shop, db, make_customer):
    make_customer("Tanvir")  # the new customer clashes: nothing is saved
    response = client.post(
        f"/shops/{shop['id']}/parse/confirm",
        json=confirm_body(timing={"duration_ms": 5000, "input": "typed"}),
    )
    assert response.status_code == 409
    assert timings(db) == []


def test_dashboard_shows_the_median_of_the_latest_50(client, shop, db):
    dashboard = client.get(f"/shops/{shop['id']}/dashboard").json()
    assert dashboard["entry_speed"] == {"median_seconds": None, "samples": 0}

    start = datetime(2026, 10, 1, tzinfo=UTC)
    # 10 old slow ones, then 50 recent ones of 1..50 seconds: the old ones don't count.
    durations = [600_000] * 10 + [s * 1000 for s in range(1, RECENT_ENTRIES + 1)]
    for i, ms in enumerate(durations):
        db.add(
            EntryTiming(
                shop_id=shop["id"], duration_ms=ms, input_method=InputMethod.TYPED,
                entry_count=1, created_at=start + timedelta(minutes=i),
            )
        )  # fmt: skip
    db.commit()

    speed = client.get(f"/shops/{shop['id']}/dashboard").json()["entry_speed"]
    assert speed == {"median_seconds": 25.5, "samples": 50}


def test_other_shops_timings_dont_count(client, shop, other_shop):
    client_body = confirm_body(timing={"duration_ms": 4000, "input": "typed"})
    assert client.post(f"/shops/{shop['id']}/parse/confirm", json=client_body).status_code == 201

    other = client.get(f"/shops/{other_shop['id']}/dashboard", headers=other_shop["headers"])
    assert other.json()["entry_speed"] == {"median_seconds": None, "samples": 0}
    mine = client.get(f"/shops/{shop['id']}/dashboard").json()["entry_speed"]
    assert mine == {"median_seconds": 4.0, "samples": 1}


def test_deleting_the_account_deletes_its_timings(client, shop, db):
    body = confirm_body(timing={"duration_ms": 4000, "input": "typed"})
    assert client.post(f"/shops/{shop['id']}/parse/confirm", json=body).status_code == 201
    response = client.request("DELETE", "/auth/me", json={"password": "secret-pass-1"})
    assert response.status_code == 204
    assert timings(db) == []
