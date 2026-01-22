terraform {
  backend "gcs" {
    bucket = "probable-dream-484923-n7-tfstate"
    prefix = "default.tfstate"
  }
}