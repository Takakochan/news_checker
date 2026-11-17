output "server_ipv4" {
  description = "Public IPv4 address of the server."
  value       = hcloud_server.default.ipv4_address
}

output "server_ipv6" {
  description = "Public IPv6 address of the server."
  value       = hcloud_server.default.ipv6_address
}
