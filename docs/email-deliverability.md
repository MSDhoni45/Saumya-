# Email deliverability (SPF / DKIM / DMARC)

WhatsAgent sends transactional email (invites, password resets, billing receipts)
from `noreply@whatsagent.ai` via SES / SendGrid / SMTP. Without correct DNS
records, mailbox providers (Gmail, Outlook, Yahoo) silently drop or spam these
messages. Configure all three records below before going live.

> Gmail & Yahoo enforce SPF + DKIM + DMARC for any sender that emails their
> users since Feb 2024. Missing records = guaranteed delivery failures.

---

## 1. Pick a sending domain

We send from the **same root domain as the app** so the From-address is
recognisable to recipients (`@whatsagent.ai`, not `@sendgrid.net`). Use a
dedicated subdomain (`mg.whatsagent.ai` or `mail.whatsagent.ai`) if you ever
need to isolate transactional reputation from marketing reputation.

## 2. SPF — authorise the sending IPs

Single `TXT` record at the apex. **Only one SPF record per domain** — merge
mechanisms if multiple providers send mail.

| Provider | `include:` mechanism |
| --- | --- |
| Amazon SES | `include:amazonses.com` |
| SendGrid | `include:sendgrid.net` |
| Postmark | `include:spf.mtasv.net` |
| Google Workspace (your own outbound) | `include:_spf.google.com` |

```
whatsagent.ai.   TXT   "v=spf1 include:amazonses.com include:sendgrid.net -all"
```

`-all` (hard fail) is correct for a domain you control end-to-end. Use `~all`
(soft fail) only during initial rollout while you confirm no legitimate sender
is missing from the include list.

## 3. DKIM — cryptographically sign every message

Each ESP generates a public-key pair; you publish the public half as a
`CNAME` (SES / SendGrid) or `TXT` (Postmark) record. Records and selectors are
copy-paste from each provider's console; common shapes:

```
# SES (3 CNAMEs, one per rotated key)
xxxx._domainkey.whatsagent.ai.   CNAME   xxxx.dkim.amazonses.com.
yyyy._domainkey.whatsagent.ai.   CNAME   yyyy.dkim.amazonses.com.
zzzz._domainkey.whatsagent.ai.   CNAME   zzzz.dkim.amazonses.com.

# SendGrid (2 CNAMEs)
s1._domainkey.whatsagent.ai.   CNAME   s1.domainkey.uXXXXX.wl.sendgrid.net.
s2._domainkey.whatsagent.ai.   CNAME   s2.domainkey.uXXXXX.wl.sendgrid.net.
```

Verify in the ESP console (each shows green ✓ once DNS propagates, usually
< 30 min). DKIM verification failures will not be obvious from the app side —
always confirm green in the provider dashboard.

## 4. DMARC — tell receivers what to do on auth failure

Single `TXT` record at `_dmarc.whatsagent.ai`.

```
_dmarc.whatsagent.ai.   TXT   "v=DMARC1; p=none; rua=mailto:dmarc-reports@whatsagent.ai; fo=1; adkim=s; aspf=s"
```

Roll the policy gradually:

1. `p=none` — monitor for 2 weeks. Check `rua` reports for any legitimate
   mail failing alignment.
2. `p=quarantine; pct=25` → `pct=100`.
3. `p=reject` — final state. Spoofed mail is bounced outright.

Do **not** start at `p=reject`. A forgotten internal sender (CI, marketing,
support helpdesk) will silently fail and the first signal will be an angry
customer.

## 5. Optional: BIMI (brand logo in Gmail)

Once `p=quarantine` or `p=reject` is live, publish a BIMI record so Gmail shows
your logo next to outbound mail. Requires a VMC certificate (~$1.5k/yr) — skip
until post-launch.

---

## Verification checklist

Before the first real send:

- [ ] `dig +short TXT whatsagent.ai` returns one SPF record covering every ESP we use.
- [ ] `dig +short CNAME <selector>._domainkey.whatsagent.ai` resolves for each DKIM key.
- [ ] `dig +short TXT _dmarc.whatsagent.ai` returns the DMARC policy.
- [ ] Send a test from the app to a Gmail + Outlook inbox. View original →
      confirm SPF / DKIM / DMARC all read `PASS`.
- [ ] mail-tester.com score ≥ 9/10.
- [ ] Provider dashboard shows verified-sender status (green).

## Application-side checklist

- [ ] `EMAIL_FROM_ADDRESS` in `apps/api/.env` uses the configured sending domain.
- [ ] `EMAIL_FROM_NAME` reads as a human brand ("WhatsAgent", not "noreply").
- [ ] Bounces + complaints are wired to a monitored inbox (or SES SNS topic).
- [ ] Unsubscribe / list-management headers (`List-Unsubscribe`) included for
      anything that isn't strictly transactional — Gmail demands this for bulk
      mail and treats borderline mail as bulk.
