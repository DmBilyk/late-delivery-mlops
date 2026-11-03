output "ec2_public_ip" {
  value = aws_instance.app.public_ip
}

output "ssh" {
  value = "ssh mlops@${aws_instance.app.public_ip}"
}

output "tunnel" {
  description = "Then open localhost:8080 (Airflow), :5001 (MLflow), :3000 (Grafana), :8000 (API)"
  value       = "ssh -N -L 8080:localhost:8080 -L 5001:localhost:5001 -L 3000:localhost:3000 -L 8000:localhost:8000 mlops@${aws_instance.app.public_ip}"
}

output "rds_endpoint" {
  value = aws_db_instance.main.address
}

output "bucket" {
  value = aws_s3_bucket.data.bucket
}

output "grafana_password_command" {
  value = "aws ssm get-parameter --name ${local.ssm_prefix}/grafana_admin_password --with-decryption --query Parameter.Value --output text"
}
