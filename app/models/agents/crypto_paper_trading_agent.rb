module Agents
  class CryptoPaperTradingAgent < Agent
    cannot_be_scheduled!

    description <<~MD
      The Crypto Paper Trading Agent simulates spot buys and sells from Coinbase Market Agent events. It never
      connects to an exchange or places orders. Buy signals add a simulated position up to the configured exposure
      limit; sell signals close the entire simulated position. A pause blocks new buys but still allows exits.

      Configure a starting balance, per-order amount, maximum position value, and daily realized-loss limit.
      All values are in USD. Events are emitted for every valid market update, including updates where no simulated
      trade was made, so they can be reviewed or forwarded to notification Agents.
    MD

    event_description <<~MD
      Events include `paper_only`, `product_id`, `action`, `reason`, `price`, `cash_usd`, `position_units`,
      `position_value_usd`, `equity_usd`, `realized_pnl_usd`, and `daily_realized_pnl_usd`.
    MD

    def default_options
      {
        'product_id' => 'BTC-USD',
        'starting_balance_usd' => '1000',
        'order_size_usd' => '25',
        'max_position_usd' => '100',
        'daily_loss_limit_usd' => '25',
        'paused' => false
      }
    end

    def working?
      last_receive_at && last_receive_at > 1.day.ago && !recent_error_logs?
    end

    def validate_options
      errors.add(:base, "product_id must be a Coinbase spot product such as BTC-USD") unless product_id_valid?
      errors.add(:base, "starting_balance_usd must be greater than 0") unless positive_option?('starting_balance_usd')
      errors.add(:base, "order_size_usd must be greater than 0") unless positive_option?('order_size_usd')
      errors.add(:base, "max_position_usd must be greater than 0") unless positive_option?('max_position_usd')
      errors.add(:base, "daily_loss_limit_usd must be greater than 0") unless positive_option?('daily_loss_limit_usd')
      validate_limits
      errors.add(:base, "paused must be true or false") if boolify(options['paused']).nil?
    end

    def receive(incoming_events)
      incoming_events.each do |event|
        payload = event.payload
        next unless valid_market_event?(payload)

        price = Float(payload['price'])
        state = portfolio
        reset_daily_loss_if_needed(state)
        action, reason = apply_signal(state, payload['signal'], price)

        create_event payload: {
          'paper_only' => true,
          'product_id' => product_id,
          'action' => action,
          'reason' => reason,
          'price' => price,
          'cash_usd' => state['cash_usd'].round(2),
          'position_units' => state['position_units'].round(8),
          'position_value_usd' => (state['position_units'] * price).round(2),
          'equity_usd' => (state['cash_usd'] + state['position_units'] * price).round(2),
          'realized_pnl_usd' => state['realized_pnl_usd'].round(2),
          'daily_realized_pnl_usd' => state['daily_realized_pnl_usd'].round(2)
        }
      end
    end

    private

    PRODUCT_ID_FORMAT = /\A[A-Z0-9]{2,12}-[A-Z0-9]{2,12}\z/
    SIGNALS = %w[buy sell hold].freeze

    def product_id
      options['product_id'].to_s
    end

    def product_id_valid?
      PRODUCT_ID_FORMAT.match?(product_id)
    end

    def numeric_option(name)
      Float(options[name])
    rescue ArgumentError, TypeError
      nil
    end

    def positive_option?(name)
      number = numeric_option(name)
      number&.finite? && number.positive?
    end

    def validate_limits
      starting_balance = numeric_option('starting_balance_usd')
      order_size = numeric_option('order_size_usd')
      max_position = numeric_option('max_position_usd')
      loss_limit = numeric_option('daily_loss_limit_usd')

      errors.add(:base, "max_position_usd cannot exceed starting_balance_usd") if starting_balance && max_position && max_position > starting_balance
      errors.add(:base, "order_size_usd cannot exceed max_position_usd") if order_size && max_position && order_size > max_position
      errors.add(:base, "daily_loss_limit_usd cannot exceed starting_balance_usd") if starting_balance && loss_limit && loss_limit > starting_balance
    end

    def valid_market_event?(payload)
      payload.is_a?(Hash) &&
        payload['exchange'] == 'coinbase' &&
        payload['product_id'] == product_id &&
        SIGNALS.include?(payload['signal']) &&
        positive_finite_number?(payload['price'])
    end

    def positive_finite_number?(value)
      number = Float(value)
      number.finite? && number.positive?
    rescue ArgumentError, TypeError
      false
    end

    def portfolio
      memory['portfolio'] ||= {
        'cash_usd' => numeric_option('starting_balance_usd'),
        'position_units' => 0.0,
        'cost_basis_usd' => 0.0,
        'realized_pnl_usd' => 0.0,
        'daily_realized_pnl_usd' => 0.0,
        'daily_loss_date' => Date.current.iso8601
      }
    end

    def reset_daily_loss_if_needed(state)
      return if state['daily_loss_date'] == Date.current.iso8601

      state['daily_loss_date'] = Date.current.iso8601
      state['daily_realized_pnl_usd'] = 0.0
    end

    def apply_signal(state, signal, price)
      if signal == 'buy'
        buy(state, price)
      elsif signal == 'sell'
        sell(state, price)
      else
        ['hold', 'No buy or sell signal']
      end
    end

    def buy(state, price)
      return ['hold', 'Paper trading is paused'] if boolify(options['paused'])
      if state['daily_realized_pnl_usd'] <= -numeric_option('daily_loss_limit_usd')
        return ['hold', 'Daily realized-loss limit reached']
      end

      remaining_capacity = numeric_option('max_position_usd') - state['cost_basis_usd']
      amount = [numeric_option('order_size_usd'), state['cash_usd'], remaining_capacity].min
      return ['hold', 'Order, cash, or maximum-position limit prevents a buy'] unless amount.positive?

      units = amount / price
      state['cash_usd'] -= amount
      state['position_units'] += units
      state['cost_basis_usd'] += amount
      ['paper_buy', 'Buy signal; simulated spot buy within configured limits']
    end

    def sell(state, price)
      return ['hold', 'No simulated position to sell'] unless state['position_units'].positive?

      proceeds = state['position_units'] * price
      pnl = proceeds - state['cost_basis_usd']
      state['cash_usd'] += proceeds
      state['realized_pnl_usd'] += pnl
      state['daily_realized_pnl_usd'] += pnl
      state['position_units'] = 0.0
      state['cost_basis_usd'] = 0.0
      ['paper_sell', 'Sell signal; simulated position closed']
    end
  end
end
