variable "region" {
  type        = string
  default     = "eu-north-1"
}

variable "project" {
  type    = string
  default = "late-delivery"
}

variable "allowed_ssh_cidr" {
  type        = string
}

variable "ssh_public_key_path" {
  type    = string
  default = "~/.ssh/id_ed25519.pub"
}

variable "instance_type" {
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
  type        = string
}

variable "force_destroy_bucket" {
  type        = bool
  default     = false
}
