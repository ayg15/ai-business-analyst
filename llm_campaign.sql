SELECT
  *
FROM
  ML.GENERATE_TEXT(
    MODEL `${ref("your_gemini_model")}`,
    (
      SELECT
        *,
        -- Construct the prompt using formatting
        FORMAT("""
          You are an expert data extraction system. Your task is to extract campaign codes into a strict JSON format based on a specific hierarchy and set of rules.

          <INPUT_DATA>
          Primary Source (Campaign Name): %s
          Fallback Source (Campaign Group Name): %s
          </INPUT_DATA>

          <EXECUTION_HIERARCHY>
          1. First, attempt to extract all codes (country_code, segment_code, etc.) from the 'Primary Source'.
          2. If a specific code cannot be found in the 'Primary Source', look for that missing code in the 'Fallback Source'.
          </EXECUTION_HIERARCHY>

          <GENERAL_RULES>
          [Paste your existing general formatting/extraction rules here]
          </GENERAL_RULES>

          <COUNTRY_RULES_FOR_FALSE_POSITIVES>
          [Paste your existing country rules here to prevent false positives]
          - Note: Apply these validation rules to codes extracted from BOTH the Primary and Fallback sources.
          </COUNTRY_RULES_FOR_FALSE_POSITIVES>

          <CONVERSION_RULES>
          Apply these conversions to the final extracted values (especially if pulled from the Fallback Source):
          - If the extracted Country Code is 'USA', change it to 'US'.
          - Map the following Local US Codes to Global Codes:
            * [LocalCode1] -> [GlobalCode1]
            * [LocalCode2] -> [GlobalCode2]
          </CONVERSION_RULES>

          <OUTPUT_FORMAT>
          Return ONLY a valid, flat JSON object. Do not include markdown formatting like ```json.
          If a code cannot be reliably found after applying all rules, return null for that key.
          Expected keys: "country_code", "segment_code", "master_brand_code", "range_brand_code", "brand_denominator_code"
          </OUTPUT_FORMAT>

        """, IFNULL(campaign_name, 'NULL'), IFNULL(campaign_group_name, 'NULL')) AS prompt
      FROM ${ref("your_source_table")}
    ),
    STRUCT(0.0 AS temperature, 1024 AS max_output_tokens, TRUE AS flatten_json_output)
  )