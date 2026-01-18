-- Fluent Bit Lua Script: Extract Exception Information
-- This script extracts exception type, message, and stack trace from log messages

function extract_exception(tag, timestamp, record)
    -- Initialize exception fields if not present
    if record["exception_type"] == nil then
        record["exception_type"] = extract_exception_type(record)
    end
    
    if record["exception_message"] == nil then
        record["exception_message"] = extract_exception_message(record)
    end
    
    if record["stack_trace"] == nil then
        record["stack_trace"] = extract_stack_trace(record)
    end
    
    -- Normalize log level
    if record["level"] ~= nil then
        record["level"] = string.upper(record["level"])
    end
    
    -- Extract logger name if not present
    if record["logger"] == nil and record["log"] ~= nil then
        record["logger"] = extract_logger_name(record["log"])
    end
    
    -- Add metadata
    record["fluent_bit_processed"] = true
    record["fluent_bit_version"] = "2.2"
    
    -- Return code:
    -- 0: Keep record
    -- -1: Drop record
    -- 1: Modified record
    return 1, timestamp, record
end

-- Extract exception type from message
function extract_exception_type(record)
    local message = record["message"] or record["log"] or ""
    
    -- Java exceptions: java.lang.NullPointerException
    local java_match = string.match(message, "([%w%.]+Exception)")
    if java_match then
        return java_match
    end
    
    -- Python exceptions: ValueError, TypeError, etc.
    local python_match = string.match(message, "(%w+Error)")
    if python_match then
        return python_match
    end
    
    -- Go panics
    if string.match(message, "^panic:") then
        return "PanicError"
    end
    
    -- .NET exceptions
    local dotnet_match = string.match(message, "([%w%.]+Exception)")
    if dotnet_match then
        return dotnet_match
    end
    
    -- Generic error
    if string.match(message, "[Ee]rror") or string.match(message, "[Ee]xception") then
        return "GenericError"
    end
    
    return nil
end

-- Extract exception message
function extract_exception_message(record)
    local message = record["message"] or record["log"] or ""
    
    -- Java: Exception: message
    local java_msg = string.match(message, "Exception:%s*(.+)")
    if java_msg then
        return trim(java_msg)
    end
    
    -- Python: Error: message
    local python_msg = string.match(message, "Error:%s*(.+)")
    if python_msg then
        return trim(python_msg)
    end
    
    -- Go: panic: message
    local go_msg = string.match(message, "panic:%s*(.+)")
    if go_msg then
        return trim(go_msg)
    end
    
    -- Return full message if no specific pattern found
    return trim(message)
end

-- Extract stack trace from message
function extract_stack_trace(record)
    local message = record["message"] or record["log"] or ""
    
    -- Check if message contains stack trace indicators
    if string.match(message, "at%s+") or 
       string.match(message, "File%s+\"") or
       string.match(message, "Traceback") or
       string.match(message, "goroutine%s+") then
        return message
    end
    
    return nil
end

-- Extract logger name from log message
function extract_logger_name(log_message)
    -- Java: [com.example.ClassName]
    local java_logger = string.match(log_message, "%[([%w%.]+)%]")
    if java_logger then
        return java_logger
    end
    
    -- Python: module.submodule
    local python_logger = string.match(log_message, "(%w+%.%w+)")
    if python_logger then
        return python_logger
    end
    
    return "unknown"
end

-- Trim whitespace from string
function trim(s)
    if s == nil then
        return nil
    end
    return (s:gsub("^%s*(.-)%s*$", "%1"))
end

-- Split string by delimiter
function split(str, delimiter)
    local result = {}
    local from = 1
    local delim_from, delim_to = string.find(str, delimiter, from)
    
    while delim_from do
        table.insert(result, string.sub(str, from, delim_from-1))
        from = delim_to + 1
        delim_from, delim_to = string.find(str, delimiter, from)
    end
    
    table.insert(result, string.sub(str, from))
    return result
end
