variable "region" {
  type    = string
  default = "eu-central-1"
}

variable "project" {
  type    = string
  default = "late-delivery"
}

variable "allowed_ssh_cidr" {
  description = "Your public IP for SSH, e.g. 203.0.113.10/32 (curl -s ifconfig.me)"
  type        = string
}

variable "ssh_public_key_path" {
  type    = string
  default = "~/.ssh/id_ed25519.pub"
}

variable "instance_type" {
  description = "The stack needs ~3 GB RAM. AWS Free plan accounts: use m7i-flex.large or c7i-flex.large"
  type        = string
  default     = "t3.medium"
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "repo_url" {
  type    = string
  default = "https://github.com/DmBilyk/late-delivery-mlops.git"
}

variable "repo_branch" {
  type    = string
  default = "main"
}

variable "budget_limit_usd" {
  type    = number
  default = 30
}

variable "budget_email" {
  description = "Where budget alerts are sent"
  type        = string
}

variable "force_destroy_bucket" {
  description = "Allow terraform destroy to delete a non-empty bucket. Keep false so history survives."
  type        = bool
  default     = false
}
