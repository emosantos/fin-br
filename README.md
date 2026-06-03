# fin-br

## Data Ingestion - BCB

## Data Ingestion - Tesouro

## Nelson-Siegel Curve Fitting

Curve:

$$y(t) = \beta_0 + \beta_1 \left( \frac{1 - e^{-t/\tau}}{t/\tau} \right) + \beta_2 \left( \frac{1 - e^{-t/\tau}}{t/\tau} - e^{-t/\tau} \right)$$

Components of the Formula:
- $y(t)$: The zero-coupon yield for maturity 
- $t$.$\beta_0$ (Level): Represents the long-term interest rate. It is a constant that does not decay, as the terms multiplying it vanish as $t \to \infty$. 
- $\beta_1$ (Slope): Represents the short-term component. The term multiplying it starts at 1 and decays to 0 as maturity increases.
- $\beta_2$ (Curvature): Represents the medium-term component. The term starts at 0, increases (creating a "hump"), and eventually decays back to 0.
- $\tau$ (Tau): The decay factor. It determines the position of the "hump" or curvature in the curve.$t$: Time to maturity (usually calculated as $DU/252$ in the Brazilian market).

In a Central Bank (BACEN) context, these parameters are meaningful. $\beta_0$ is the market's view on the terminal interest rate, while $\beta_1$ and $\beta_2$ describe the current stance of monetary policy (tight vs. loose).

Smoothing: Market prices can be noisy. Nelson-Siegel "smooths" out these points, providing a more robust curve for pricing other instruments.

Foundation for Stripping: Once you have the $\beta$ parameters from your LTNs, you can calculate the discount factor for any date.

