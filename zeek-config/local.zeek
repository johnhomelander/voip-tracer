# zeek-config/local.zeek
@load base/frameworks/logging/writers/json
redef Log::default_writer = Log::WRITER_JSON;
redef SIP::log_call_id = T;
