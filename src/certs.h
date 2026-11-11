#pragma once

// Root CA bundle for all HTTPS endpoints (open.bigmodel.cn).
// Multiple anchors so the device survives a server-side CA rotation:
//   WoTrus RSA DV SSL CA 2 — served intermediate (expires 2035-08-19)
//   Sectigo R46, USERTrust-cross-signed — served chain anchor (expires 2038-01-18)
//   USERTrust RSA Certification Authority — self-signed root (expires 2038-01-18)
// 2026-10: the site rotated from TrustAsia->Certum to WoTrus->Sectigo->USERTrust,
// which broke TLS until this re-pin. Rotation history lives in ../../zhipu-usage-stick-certs/.
extern const char CA_BUNDLE[];
