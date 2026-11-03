data "aws_ssm_parameter" "ubuntu_ami" {
  name = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}

resource "aws_key_pair" "main" {
  key_name   = var.project
  public_key = file(pathexpand(var.ssh_public_key_path))
}

resource "aws_instance" "app" {
  ami                    = data.aws_ssm_parameter.ubuntu_ami.value
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.ec2.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = aws_key_pair.main.key_name

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    region      = var.region
    ssm_prefix  = local.ssm_prefix
    repo_url    = var.repo_url
    repo_branch = var.repo_branch
  })

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
    encrypted   = true
  }

  # IMDSv2 only; hop limit 2 so containers (one extra network hop) can get the role credentials.
  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  # The startup script reads these on first boot.
  depends_on = [
    aws_ssm_parameter.db_host,
    aws_ssm_parameter.db_password,
    aws_ssm_parameter.bucket,
    aws_ssm_parameter.grafana_password,
  ]

  # A new Ubuntu AMI must not recreate the machine on every apply. Rebuild on purpose with -replace.
  lifecycle {
    ignore_changes = [ami]
  }

  tags = { Name = var.project }
}
