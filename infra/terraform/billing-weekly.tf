resource "google_bigquery_dataset" "billing_export" {
  count      = var.billing_weekly_summary_enabled ? 1 : 0
  project    = var.project_id
  dataset_id = var.billing_export_dataset
  location   = var.billing_export_dataset_location

  delete_contents_on_destroy = false
}

resource "google_cloud_run_v2_job" "billing_weekly" {
  count    = var.billing_weekly_summary_enabled ? 1 : 0
  provider = google-beta
  name     = var.billing_weekly_job_name
  location = var.region

  template {
    template {
      service_account = google_service_account.billing_report.email

      containers {
        image   = "gcr.io/google.com/cloudsdktool/cloud-sdk:slim"
        command = ["bash", "-c"]
        args = [
          <<-EOT
          set -euo pipefail

          PROJECT_ID="$${PROJECT_ID}"
          DATASET="$${BILLING_EXPORT_DATASET}"
          TABLE="$${BILLING_EXPORT_TABLE}"

          QUERY="SELECT ROUND(SUM(cost) + IFNULL(SUM((SELECT SUM(c.amount) FROM UNNEST(credits) c)), 0), 2) AS total_cost FROM \`$${PROJECT_ID}.$${DATASET}.$${TABLE}\` WHERE usage_start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)"
          TOTAL=$(bq --project_id="$${PROJECT_ID}" query --use_legacy_sql=false --format=csv "$${QUERY}" | tail -n 1 | tr -d '\\r')
          if [ -z "$${TOTAL}" ] || [ "$${TOTAL}" = "total_cost" ]; then
            TOTAL="0"
          fi

          START_DATE=$(date -u -d '7 days ago' +%F)
          END_DATE=$(date -u +%F)
          MESSAGE="Weekly spend ($${START_DATE} to $${END_DATE} UTC): $${TOTAL} USD"

          PAYLOAD=$(printf '{"text":"%s"}' "$${MESSAGE}")
          curl -sS -X POST -H 'Content-type: application/json' --data "$${PAYLOAD}" "$${BILLING_SLACK_WEBHOOK_URL}"
          EOT
        ]

        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "BILLING_EXPORT_DATASET"
          value = var.billing_export_dataset
        }

        env {
          name  = "BILLING_EXPORT_TABLE"
          value = local.billing_export_table
        }

        env {
          name = "BILLING_SLACK_WEBHOOK_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.secrets["BILLING_SLACK_WEBHOOK_URL"].secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }
}

resource "google_cloud_scheduler_job" "billing_weekly" {
  count     = var.billing_weekly_summary_enabled ? 1 : 0
  name      = "${var.billing_weekly_job_name}-schedule"
  region    = var.region
  schedule  = var.billing_weekly_summary_cron
  time_zone = var.billing_weekly_summary_timezone

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.billing_weekly[0].name}:run"
    oauth_token {
      service_account_email = google_service_account.billing_report.email
    }
  }
}
