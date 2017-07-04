contract Token is StandardToken {
    // token contract just manages tokens, has no idea of issuance/destroying price or policy
    function Token(prealloc) {}; //
    function registerMint(address _mint) isOwner {}; // registeres the mint address
    function totalSupply() {}; //
    function transfer(_to, value) {}; //
    function balanceOf(address) {}; //
    function issue(num, recipient) {} is Mint; // can only be called by Mint which is fully trusted
    function destroy(num, owner) {} is Mint; // can only be called by Mint which is fully trusted
}


contract Mint {
    /// sets the price based on the Token.totalSupply using the Curve
    /// manages the reserve (ETH)

    enum Stages {
        MintDeployed,
        MintSetUp, // after Auction address is registered
        AuctionEnded, // after Auction called
        TradingStarted
    }

    function __init__(factor=1., base_price=0, beneficiary, token) {}; //
    function registerAuction(_auction) isOwner atStage(Stages.MintDeployed) {
         // registeres the mint address
         // transition to Stages.MintSetUp
        };
    function curve_price(supply) {}; //
    function curve_supply(reserve) constant {}; //
    function curve_supply_at_price(price) constant {}; //
    function curve_reserve(supply) constant {}; //
    function curve_reserve_at_price(price) constant {}; //
    function curve_cost(supply, num) constant {}; //
    function curve_newly_issuable(supply, added_reserve) constant {}; //
    function curve_mktcap(supply) constant {}; //
    function curve_supply_at_mktcap(m) constant {}; //
    function sale_cost(num, supply) constant {}; //  # cost
    function purchase_cost(num, supply) constant {}; //
    function isauction(self) constant {}; //
    function ask() constant {}; //
    function bid() constant {}; //
    function mktcap() constant {}; //
    function valuation() constant {}; //  # (ask - bid) * supply
    /// non constant funcs
    function buy() atStage(Stages.TradingStarted) {
        // msg.sender, msg.value
        // Q: should we have a fallback function which triggers buy?
        // sent eth is implicity received as reserve, which is the ETH at the Mint account (this.value)
        // calc the num of newly issued tokens based on the eth amount sent
        // call token.issue(msg.sender, num)
    }
    function sell(num) atStage(Stages.TradingStarted) {
        // num tokens are destroyed from msg.sender and the purchase cost is credited to him
        // token.destroy(account, num);
        // send.value(msg.sender, eth_amount); ## FIXME
    }
    function funds_from_auction() atStage(Stages.MintSetUp) isAuction {
        // receives ETH sent by auction
        // transition to Stage.AuctionEnded

    function issue_from_auction(recipient, num) atStage(Stages.AuctionEnded) isAuction {
        // called from Auction.claimTokens
        // calls token.issue(recipient, num)
    }
    function startTrading() atStage(Stages.AuctionEnded) isAuction {
        // called from auction once all tokens are issued
    }

}

contract DutchAuction {
    enum Stages {
        AuctionDeployed,
        AuctionSetUp, // after Mint address is registered
        AuctionStarted, //
        AuctionEnded, //
        AuctionSettled // once all tokens have been issued
    }

    uint received_value;
    uint total_issuance;
    uint issued_value;
    mapping (address => uint256) funds;

    function __init__(factor, const) {}; //
    function price() constant {
        // over time decaying price function. no need to calculate price based on simulated supply
    };
    function isactive() constant {
        // true if this.price > mint.curve_price_at_reserve(this.value)
        // modelled as atStage(Stages.AuctionStarted)
    };
    function missing_reserve_to_end_auction() constant {};
    function max_mktcap() constant {}; // the mktcap if the auction would end at the current price
    function max_valuation() constant {}; // the valuation if the auction would end at the current price
    function order() atStage(Stages.AuctionStarted) {
        // msg.sender, msg.value
        // Q: should we have a fallback function which triggers bid?
        // sent eth is implicity received as reserve, which is the ETH at the DutchAuction account (this.value)
        accepted_value = max(this.missing_reserve_to_end_auction(), msg.value);
        funds[msg.sender] += accepted_value; // register number of ETH accepted from msg.sender
        if (account_value < msg.value) {
            // refund excess ETH
            // auction ended
            this.finalize_auction();
        }
    };
    function finalize_auction() atStage(Stages.AuctionStarted) {
        // require this.price <= mint.curve_price_at_reserve(this.value)
        // transition to next Stages.AuctionEnded
        received_value = this.value;
        total_issuance = Mint.curve.supply(reserve + Mint.value); // note, there could be a reserve already from the prealloc
        Mint.funds_from_auction.value(this.value);  // send funds
        };
    function claimTokens(recipients) atStage(Stages.AuctionEnded) {
        // called multiple times (gas limit!) until all bidders got their tokens
        for recipient in recipients:
            num = funds[recipient] * total_issuance / received_value;
            issued_value += funds[recipient];
            funds[recipient] = 0;
            mint.issue_from_auction(recipient, num);

        if (issued_value == received_value) {
            // transition to States.AuctionSettled;
            // call Mint.startTrading;
        }
    };
}
