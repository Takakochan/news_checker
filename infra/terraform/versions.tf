terraform {
  required_version = ">= 1.9"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = ">= 1.45, < 2.0"
    }
  }
}

# Token comes from the HCLOUD_TOKEN environment variable, never from a file in this repo.
provider "hcloud" {}
