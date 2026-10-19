require 'json'

module Agents
  class CoinbaseMarketAgent < Agent
    include WebRequestConcern

    default_schedule "every_1m"

    description <<~MD
      The Coinbase Market Agent polls Coinbase's public spot ticker and emits price events with a simple,
      configurable one-interval percentage-move signal. It does not require API credentials and never places orders.

      `product_id` defaults to `BTC-USD`. `signal_threshold_percent` is the absolute percentage change required
      for a `buy` or `sell` signal; the first price sample is always `hold`. These signals are examples for
      monitoring and paper trading, not investment advice.

      Connect this Agent to a Paper Trading Agent to simulate trades. Connect it to notification Agents to receive
      alerts. The `expected_update_period_in_days` option controls the working status.
    MD

    event_description <<~MD
      Events contain `exchange`, `product_id`, `price`, `volume_24h`, `change_percent`, `signal` (`buy`, `sell`,
      or `hold`), and `timestamp`. Signals are based on the price change since the previous successful poll.
    MD

    def default_options
      {
        'product_id' => 'BTC-USD',
        'signal_threshold_percent' => '1.0',
        'expected_update_period_in_days' => '1',
        'disable_redirect_follow' => true
      }
    end

    def parse_body?
      true
    end

    def working?
      event_created_within?(interpolated['expected_update_period_in_days'].presence || 1) && !recent_error_logs?
    end

    def validate_options
      errors.add(:base, "product_id must be a Coinbase spot product such as BTC-USD") unless product_id_valid?
      errors.add(:base, "signal_threshold_percent must be greater than 0 and at most 100") unless valid_threshold?
      errors.add(:base, "expected_update_period_in_days must be greater than 0") unless valid_expected_update_period?
    end

    def check
      response = faraday.get("https://api.exchange.coinbase.com/products/#{product_id}/ticker")
      unless response.status == 200
        error("Coinbase ticker request returned HTTP #{response.status}")
        return
      end

      ticker = response.body.is_a?(String) ? JSON.parse(response.body) : response.body
      unless ticker.is_a?(Hash)
        error("Coinbase ticker response was not an object")
        return
      end
      price = positive_finite_number(ticker['price'])
      unless price
        error("Coinbase ticker response did not contain a valid price")
        return
      end

      previous_price = positive_finite_number(memory['last_price'])
      change_percent = previous_price ? ((price / previous_price) - 1) * 100 : 0.0
      threshold = numeric_option('signal_threshold_percent')
      signal = if previous_price.nil?
                 'hold'
               elsif change_percent >= threshold
                 'buy'
               elsif change_percent <= -threshold
                 'sell'
               else
                 'hold'
               end

      create_event payload: {
        'exchange' => 'coinbase',
        'product_id' => product_id,
        'price' => price,
        'volume_24h' => positive_finite_number(ticker['volume']) || 0.0,
        'change_percent' => change_percent.round(6),
        'signal' => signal,
        'timestamp' => ticker['time'].presence || Time.current.iso8601
      }
      memory['last_price'] = price
    rescue Faraday::Error, JSON::ParserError, TypeError => e
      error("Failed to read Coinbase ticker: #{e.class}")
    end

    private

    PRODUCT_ID_FORMAT = /\A[A-Z0-9]{2,12}-[A-Z0-9]{2,12}\z/

    def product_id
      interpolated['product_id'].to_s
    end

    def product_id_valid?
      PRODUCT_ID_FORMAT.match?(options['product_id'].to_s)
    end

    def numeric_option(name)
      Float(interpolated[name])
    rescue ArgumentError, TypeError
      nil
    end

    def valid_threshold?
      threshold = numeric_option('signal_threshold_percent')
      threshold&.finite? && threshold.positive? && threshold <= 100
    end

    def valid_expected_update_period?
      period = numeric_option('expected_update_period_in_days')
      period&.finite? && period.positive?
    end

    def positive_finite_number(value)
      number = Float(value)
      number if number.finite? && number.positive?
    rescue ArgumentError, TypeError
      nil
    end
  end
end
