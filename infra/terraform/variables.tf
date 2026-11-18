variable "server_name" {
  description = "Name of the Hetzner Cloud server (and prefix for related resources)."
  type        = string
  default     = "news-checker"
}

variable "location" {
  description = "Hetzner Cloud location (fsn1, nbg1, hel1, ash, hil)."
  type        = string
  default     = "fsn1"
}

variable "server_type" {
  description = "Hetzner Cloud server type."
  type        = string
  default     = "cx33"
}

variable "ssh_public_key_path" {
  description = "Path to the SSH public key to register on the server."
  type        = string
  default     = "~/.ssh/id_ed25519.pub"
}

variable "allowed_ssh_cidrs" {
  description = "CIDR ranges allowed to reach port 22. Narrow this down once you know your fixed source IP."
  type        = list(string)
  default     = ["0.0.0.0/0", "::/0"]
}
