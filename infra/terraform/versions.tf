terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }

  # State is kept locally (terraform.tfstate, git-ignored). For a team, move it to
  # S3 with a backend "s3" block; see specs/003-aws-deployment/design.md.
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      project    = var.app_name
      managed-by = "terraform"
    }
  }
}
