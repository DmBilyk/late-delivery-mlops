# S3: MLflow artifacts (mlartifacts/) and batch predictions (predictions/).
resource "random_id" "bucket" {
  byte_length = 4
}

resource "aws_s3_bucket" "data" {
  bucket        = "${var.project}-${random_id.bucket.hex}"
  force_destroy = var.force_destroy_bucket
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# RDS: databases ml (created here), mlflow and airflow (created by src.init_db on first boot).
resource "random_password" "db" {
  length  = 24
  special = false # the password goes into connection URLs
}

resource "aws_db_subnet_group" "main" {
  name       = var.project
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_instance" "main" {
  identifier              = "${var.project}-db"
  engine                  = "postgres"
  engine_version          = "16"
  instance_class          = var.db_instance_class
  allocated_storage       = 20
  storage_type            = "gp3"
  db_name                 = "ml"
  username                = "ml"
  password                = random_password.db.result
  db_subnet_group_name    = aws_db_subnet_group.main.name
  vpc_security_group_ids  = [aws_security_group.rds.id]
  publicly_accessible     = false
  multi_az                = false
  backup_retention_period = 1
  skip_final_snapshot     = true
  apply_immediately       = true
}

# SSM Parameter Store: the EC2 startup script builds .env from these. No secrets in user data or git.
resource "random_password" "grafana" {
  length  = 20
  special = false
}

locals {
  ssm_prefix = "/${var.project}"
}

resource "aws_ssm_parameter" "db_host" {
  name  = "${local.ssm_prefix}/db_host"
  type  = "String"
  value = aws_db_instance.main.address
}

resource "aws_ssm_parameter" "db_password" {
  name  = "${local.ssm_prefix}/db_password"
  type  = "SecureString"
  value = random_password.db.result
}

resource "aws_ssm_parameter" "bucket" {
  name  = "${local.ssm_prefix}/bucket"
  type  = "String"
  value = aws_s3_bucket.data.bucket
}

resource "aws_ssm_parameter" "grafana_password" {
  name  = "${local.ssm_prefix}/grafana_admin_password"
  type  = "SecureString"
  value = random_password.grafana.result
}
