provider "google" {
  project = "edikte-analytics-2026"
}

terraform {
	required_providers {
		google = {
	    version = "~> 5.45.2"
		}
  }
}
