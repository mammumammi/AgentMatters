# TriGuard - Developer Feedback

## Gensyn AXL Feedback
- **The Good:** The architecture of having a local API gateway handle the complex Yggdrasil routing is brilliant. It makes integrating P2P networking into Python scripts incredibly easy.
- **The Friction:** We encountered significant issues testing locally. MacOS does not natively route the Yggdrasil IPv6 overlay addresses, meaning nodes on the same machine cannot reach each other via their public Yggdrasil IPs unless a TUN interface is manually configured.
- **The Solution:** We discovered that by setting `tcp_port: 7000` consistently across all local nodes, the internal gVisor network allowed the nodes to find each other via the Gensyn backbone. This should be explicitly documented in the AXL `examples/` for developers testing multi-node setups locally.

## KeeperHub Feedback
- **The Good:** The webhook interface is incredibly fast and the visual workflow builder makes it easy to route consensus alerts to Discord without writing boilerplate integration code.
- **The Friction:** Authentication documentation is slightly confusing regarding Webhooks. The dashboard provides `kh_` API keys, which return a 401 Unauthorized for webhook endpoints. It took reading through disparate documentation to realize that webhooks specifically require a `wfb_` (User Key) generated from a different part of the dashboard.
- **The Solution:** A small tooltip or clearer error message on the Webhook Node UI stating "Requires a wfb_ prefixed User Key" would save developers a lot of debugging time.
