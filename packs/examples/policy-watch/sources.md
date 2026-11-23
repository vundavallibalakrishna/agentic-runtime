The sources the policy watch reads, and the settings it uses. Edit this skill to change
what is watched: add a source, remove one, or name your own policy collections. Publish
the skill after editing so the next run uses it.

```yaml
sources:
  - name: RBI notifications (feed)
    url: https://www.rbi.org.in/notifications_rss.xml
    watch: feed          # feed: list the items, keep each new one
  - name: RBI notifications (page)
    url: https://www.rbi.org.in/Scripts/NotificationUser.aspx
    watch: page          # page: keep a copy when the content changes, and diff it

# Knowledge collections that hold your own policies. The watch searches these for the
# sections a change touches. Leave empty to skip that step.
internal_collections: []

# Hours a change on an official page may wait for a matching item from a licensed feed
# before the watch reports it as missed by the feed. Used only when vendor_feeds is set.
lag_window_hours: 48

# Licensed feeds, when a feed connector is installed. Each entry names the connector and
# the official sources it covers. Empty means every source above is watched in full.
vendor_feeds: []
```

How to read `watch`:

- `feed` is for an RSS or Atom feed, or a sitemap. The watch lists its items and keeps a
  copy of each item it has not seen.
- `page` is for a single page. The watch keeps a copy each time the content changes and
  compares the new copy with the one before.

The hosts of every address above must be on your organisation's list of hosts tools may
reach (Policies, Web access).
