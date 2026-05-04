# Operations Runbook

## Backup
- Create sqlite backup:
  - `npm run db:backup`
- Backups are written to `BACKUP_DIR` (default: `./backups`).

## Restore
- Restore from backup:
  - `npm run db:restore -- --from ./backups/tcg_trove-YYYYMMDDTHHMMSSZ.db`

## Data Retention
- Run retention cleanup:
  - `npm run data:retention`
- This prunes:
  - `inquiry_messages` older than `INQUIRY_MESSAGE_RETENTION_DAYS`
  - `search_logs` older than `SEARCH_LOG_RETENTION_DAYS`
  - `audit_logs` older than `AUDIT_LOG_RETENTION_DAYS`
  - uploads older than `MEDIA_UPLOAD_RETENTION_DAYS`

## Rollback Plan
1. Stop app traffic.
2. Restore latest known-good backup.
3. Start app and verify:
   - `/health/live`
   - `/health/ready`
   - `/metrics` (with auth token)
4. Run smoke tests (`npm run ui:parallel`) before reopening traffic.

## Messaging SRE Notes
- New threaded replies are stored in `inquiry_messages`.
- Poll endpoint: `GET /messages/{inquiry_id}/events`.
- Counters exposed:
  - `tcg_trove_message_replies_total`
  - `tcg_trove_message_poll_total`

